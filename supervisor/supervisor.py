import time
import logging
import redis
import json
import os
import sqlalchemy

from db_utils import (
    get_db,
    get_stuck_tasks,
    requeue_task,
    get_inactive_workers,
    ControllerTask,
)
from notify import send_email, send_telegram
from reoptimize_utils import reoptimize_by_metric
import config

# --- Use status constants from db.status_constants ---
from db.status_constants import (
    JOB_STATUS_NEW,
    JOB_STATUS_QUEUED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_COMPLETED_SUCCESS,
    JOB_STATUS_COMPLETED_PARTIAL,
    JOB_STATUS_FAILED,
)

logging.basicConfig(level=logging.INFO)

def notify_task_retry(task, attempt_count):
    subject = f"[Task Retry] {task.file_path or '(unknown)'} | Task ID: {task.id}"
    body = (
        f"Task for set file: {task.file_path or '(unknown)'}\n"
        f"Task ID: {task.id}\n"
        f"Job ID: {task.job_id}\n"
        f"Attempt: {attempt_count + 1}/{task.max_attempts}\n"
        f"Status: Retrying due to previous failure or inactivity."
    )
    send_email(subject, body)
    send_telegram(body)

def notify_task_failed(task):
    subject = f"[Task Failed] {task.file_path or '(unknown)'} | Task ID: {task.id}"
    body = (
        f"Task for set file: {task.file_path or '(unknown)'}\n"
        f"Task ID: {task.id}\n"
        f"Job ID: {task.job_id}\n"
        f"Status: Permanently failed after {task.max_attempts} attempts.\n"
        f"Manual intervention may be required."
    )
    send_email(subject, body)
    send_telegram(body)

def notify_stuck_task(task):
    subject = f"[Task Stuck] {task.file_path or '(unknown)'} | Task ID: {task.id}"
    body = (
        f"Task for set file: {task.file_path or '(unknown)'}\n"
        f"Task ID: {task.id}\n"
        f"Job ID: {task.job_id}\n"
        f"Status: Detected as stuck/inactive for more than {config.JOB_STUCK_THRESHOLD_MINUTES} minutes."
    )
    send_email(subject, body)
    send_telegram(body)

def notify_inactive_worker(worker_id, minutes):
    subject = f"[Worker Inactive] Worker ID: {worker_id}"
    body = (
        f"Worker {worker_id} has not sent a heartbeat for over {minutes} minutes.\n"
        f"Please check the worker's status."
    )
    send_email(subject, body)
    send_telegram(body)

def build_task_data_for_redis(task):
    ea_name = None
    symbol = None
    timeframe = None
    job = getattr(task, "job", None)
    if job is not None:
        ea_name = getattr(job, "ea_name", None)
        symbol = getattr(job, "symbol", None)
        timeframe = getattr(job, "timeframe", None)
    else:
        ea_name = getattr(task, "ea_name", None)
        symbol = getattr(task, "symbol", None)
        timeframe = getattr(task, "timeframe", None)

    file_blob_key = f"task:{task.id}:input_blob"
    set_file_name = os.path.basename(task.file_path) if task.file_path else None

    return {
        "job_id": task.job_id,
        "task_id": task.id,
        "set_file_name": set_file_name,
        "input_blob_key": file_blob_key,
        "ea_name": ea_name,
        "symbol": symbol,
        "timeframe": timeframe,
    }

def ensure_file_blob_in_redis(r, task, session):
    file_blob_key = f"task:{task.id}:input_blob"
    exists = r.exists(file_blob_key)
    if not exists:
        if getattr(task, "file_blob", None):
            r.set(file_blob_key, task.file_blob)
            logging.info(f"Restored missing file_blob for task {task.id} from DB")
            return True
        else:
            task.status = JOB_STATUS_FAILED
            task.last_error = "Missing file_blob in Redis and DB"
            session.commit()
            logging.error(f"Failed to restore missing file_blob for task {task.id}; marked as failed")
            notify_task_failed(task)
            return False
    return True

def reconcile_db_redis(session, r):
    logging.info("Reconciling DB and Redis queue for 'queued' tasks...")

    main_queue_tasks = set(r.lrange(config.REDIS_MAIN_QUEUE, 0, -1))

    tasks = session.query(ControllerTask).filter_by(status=JOB_STATUS_QUEUED).all()
    requeued_count = 0
    for task in tasks:
        if task.status not in [
            JOB_STATUS_NEW,
            "retrying",
            "fine_tuning",
            JOB_STATUS_QUEUED,
        ]:
            continue

        task_data = build_task_data_for_redis(task)
        task_json = json.dumps(task_data)
        if task_json not in main_queue_tasks:
            if not ensure_file_blob_in_redis(r, task, session):
                continue
            r.lpush(config.REDIS_MAIN_QUEUE, task_json)
            requeued_count += 1
    if requeued_count:
        logging.info(f"Requeued {requeued_count} queued tasks to Redis main queue.")

def auto_reoptimize_when_idle(engine, watch_folder, user_id):
    """
    Performs auto-reoptimize if the queue is empty.
    Auto-Reoptimize Summary:
     - Prioritizes job status in the following order:
       1. JOB_STATUS_FAILED
       2. JOB_STATUS_COMPLETED_PARTIAL
       3. JOB_STATUS_COMPLETED_SUCCESS

     - Uses the view `v_test_metrics_best_per_symbol` to select the best metric for each job/symbol.
       (Ensure this view is correctly defined to truly return the best metric per job/symbol.)

     - Only selects jobs that have NOT been reoptimized yet:
       SQL: AND NOT EXISTS (SELECT 1 FROM reoptimize_history WHERE job_id = jobs.id)

     - Orders candidates by:
       ORDER BY normalized_total_distance_to_good ASC, weighted_score DESC
       (This picks the metric closest to success.)

     - LIMIT 1:
       Only one job/metric is processed per idle period.
    """
    # Use imported job status constants
    reopt_statuses = [
        JOB_STATUS_FAILED,
        JOB_STATUS_COMPLETED_PARTIAL,
        JOB_STATUS_COMPLETED_SUCCESS,
    ]

    with engine.connect() as conn:
        for status in reopt_statuses:
            sql = """
            SELECT 
                jobs.id AS job_id,
                jobs.ea_name,
                jobs.symbol,
                jobs.timeframe,
                metrics.id AS metric_id,
                metrics.set_file_name,
                COALESCE((
                    SELECT COUNT(*)
                    FROM reoptimize_history repot
                    JOIN controller_jobs cj ON repot.job_id = cj.id
                    WHERE cj.symbol = jobs.symbol
                ), 0) AS repot_sybmol_count
            FROM
                controller_jobs jobs
            JOIN controller_tasks tasks ON tasks.job_id = jobs.id
            JOIN v_test_metrics_best_per_symbol metrics ON metrics.controller_task_id = tasks.id
            WHERE
                metrics.id IS NOT NULL
                AND jobs.status = :status
            ORDER BY repot_sybmol_count ASC, normalized_total_distance_to_good ASC, weighted_score DESC
            LIMIT 1
            """
            row = conn.execute(sqlalchemy.text(sql), {"status": status}).fetchone()
            if not row:
                continue

            job_row = {
                "id": row.job_id,
                "symbol": row.symbol,
                "timeframe": row.timeframe,
                "ea_name": row.ea_name,
            }
            metric_row = {
                "metric_id": row.metric_id,
                "set_file_name": row.set_file_name,
            }
            metric_id = row.metric_id

            try:
                reoptimize_by_metric(
                    engine=engine,
                    metric_id=metric_id,
                    job_row=job_row,
                    metric_row=metric_row,
                    user_id=user_id,
                    meta_extras={
                        "auto_reoptimize": True,
                        "auto_reoptimize_status": status
                    },
                    prefix="A",
                    watch_folder=watch_folder
                )
                logging.info(f"[auto_reoptimize_when_idle] Auto re-optimized: job_id={job_row['id']} metric_id={metric_id} status={status}")
            except Exception as e:
                logging.error(f"[auto_reoptimize_when_idle] Failed to auto reoptimize job_id={job_row['id']} metric_id={metric_id}: {e}")

            # Only process one per idle period
            break

def main():
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
    if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
        DB_URL = config.SQLALCHEMY_DATABASE_URL
    else:
        DB_URL = (
            f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
            f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
        )
    engine = sqlalchemy.create_engine(DB_URL)

    while True:
        try:
            with get_db() as session:
                # --- Handle Stuck Tasks in DB ---
                stuck_tasks = get_stuck_tasks(session, threshold_minutes=config.JOB_STUCK_THRESHOLD_MINUTES)
                for task in stuck_tasks:
                    current_attempt = (task.attempt_count or 0)
                    max_attempts = task.max_attempts or 1

                    if task.status not in [JOB_STATUS_NEW, "retrying", "fine_tuning"]:
                        logging.info(f"Skipping terminal stuck task {task.id} (status: {task.status})")
                        continue

                    notify_stuck_task(task)
                    if current_attempt < max_attempts:
                        if not ensure_file_blob_in_redis(r, task, session):
                            continue
                        requeue_task(session, task)
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) stuck for over {config.JOB_STUCK_THRESHOLD_MINUTES} min. Marked as retrying (attempt {current_attempt + 1}/{max_attempts})."
                        )
                        notify_task_retry(task, current_attempt)
                    else:
                        task.status = JOB_STATUS_FAILED
                        session.commit()
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) permanently failed after {max_attempts} attempts."
                        )
                        notify_task_failed(task)

                # --- Handle Inactive Workers (unchanged) ---
                inactive_workers = get_inactive_workers(
                    session, threshold_minutes=config.WORKER_INACTIVE_THRESHOLD_MINUTES
                )
                for worker_id in inactive_workers:
                    logging.warning(
                        f"Worker {worker_id} inactive for over {config.WORKER_INACTIVE_THRESHOLD_MINUTES} min."
                    )
                    notify_inactive_worker(worker_id, config.WORKER_INACTIVE_THRESHOLD_MINUTES)

                # --- Reconcile DB and Redis queue (unchanged) ---
                reconcile_db_redis(session, r)

            # --- AUTO REOPTIMIZE WHEN QUEUE IS EMPTY ---
            if r.llen(config.REDIS_MAIN_QUEUE) == 0:
                supervisor_user_id = getattr(config, "USER_ID", 1)
                auto_reoptimize_when_idle(
                    engine=engine,
                    watch_folder=config.WATCH_FOLDER,
                    user_id=supervisor_user_id
                )

        except Exception as e:
            import traceback
            logging.error(f"Supervisor error: {e}\n{traceback.format_exc()}")
            subject = "[Supervisor Error]"
            body = f"Supervisor encountered an error: {e}"
            send_email(subject, body)
            send_telegram(body)

        time.sleep(config.SUPERVISOR_POLL_INTERVAL)

if __name__ == "__main__":
    main()