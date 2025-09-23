import time
import logging
import redis
import json
import os

from db_utils import (
    get_db,
    get_stuck_tasks,
    requeue_task,
    get_inactive_workers,
    ControllerTask,
)
from notify import send_email, send_telegram
import config

logging.basicConfig(level=logging.INFO)

def notify_task_retry(task, attempt_count):
    # Notify about a task retry attempt
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
    # Notify when a task is permanently failed
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
    # Notify when a stuck task is detected
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
    # Notify when a worker is inactive
    subject = f"[Worker Inactive] Worker ID: {worker_id}"
    body = (
        f"Worker {worker_id} has not sent a heartbeat for over {minutes} minutes.\n"
        f"Please check the worker's status."
    )
    send_email(subject, body)
    send_telegram(body)

def build_task_data_for_redis(task):
    """
    Build a task JSON dict for Redis queue, consistent with controller_utils.queue_task_to_redis.
    """
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
    """
    Ensure the file_blob for a task exists in Redis before re-queueing.
    If missing, restore from DB if possible.
    If file_blob cannot be restored, mark the task as failed.
    Returns True if file_blob is present in Redis after this call, else False.
    """
    file_blob_key = f"task:{task.id}:input_blob"
    exists = r.exists(file_blob_key)
    if not exists:
        # Try to restore from DB
        if getattr(task, "file_blob", None):
            r.set(file_blob_key, task.file_blob)
            logging.info(f"Restored missing file_blob for task {task.id} from DB")
            return True
        else:
            # Cannot restore, mark as failed and log/notify
            task.status = "failed"
            task.last_error = "Missing file_blob in Redis and DB"
            session.commit()
            logging.error(f"Failed to restore missing file_blob for task {task.id}; marked as failed")
            notify_task_failed(task)
            return False
    return True

def reconcile_db_redis(session, r):
    """
    Requeue any 'queued' tasks in DB but missing from Redis main queue.
    Only requeue eligible tasks, and ensure file_blob exists in Redis.
    """
    logging.info("Reconciling DB and Redis queue for 'queued' tasks...")

    main_queue_tasks = set(r.lrange(config.REDIS_MAIN_QUEUE, 0, -1))

    tasks = session.query(ControllerTask).filter_by(status="queued").all()
    requeued_count = 0
    for task in tasks:
        # Only requeue eligible tasks
        if task.status not in ["new", "retrying", "fine_tuning", "queued"]:
            continue

        task_data = build_task_data_for_redis(task)
        task_json = json.dumps(task_data)
        if task_json not in main_queue_tasks:
            # Ensure file_blob is present in Redis before requeue
            if not ensure_file_blob_in_redis(r, task, session):
                continue  # file_blob missing and cannot be restored, already marked as failed
            r.lpush(config.REDIS_MAIN_QUEUE, task_json)
            requeued_count += 1
    if requeued_count:
        logging.info(f"Requeued {requeued_count} queued tasks to Redis main queue.")

def main():
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
    while True:
        try:
            with get_db() as session:
                # --- Handle Stuck Tasks in DB ---
                stuck_tasks = get_stuck_tasks(session, threshold_minutes=config.JOB_STUCK_THRESHOLD_MINUTES)
                for task in stuck_tasks:
                    current_attempt = (task.attempt_count or 0)
                    max_attempts = task.max_attempts or 1

                    # Only requeue eligible tasks (not terminal)
                    if task.status not in ["new", "retrying", "fine_tuning"]:
                        logging.info(f"Skipping terminal stuck task {task.id} (status: {task.status})")
                        continue

                    notify_stuck_task(task)
                    if current_attempt + 1 < max_attempts:
                        # Ensure file_blob is present in Redis before requeue
                        if not ensure_file_blob_in_redis(r, task, session):
                            continue  # file_blob missing and cannot be restored, already marked as failed

                        requeue_task(session, task)
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) stuck for over {config.JOB_STUCK_THRESHOLD_MINUTES} min. Retrying (attempt {current_attempt + 1}/{max_attempts})."
                        )
                        notify_task_retry(task, current_attempt)
                        # Requeue in Redis main queue in controller_utils-compatible format
                        task_data = build_task_data_for_redis(task)
                        task_json = json.dumps(task_data)
                        r.lpush(config.REDIS_MAIN_QUEUE, task_json)
                    else:
                        # Max attempts reached, mark as failed
                        task.status = "failed"
                        session.commit()
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) permanently failed after {max_attempts} attempts."
                        )
                        notify_task_failed(task)

                # --- Handle Inactive Workers ---
                inactive_workers = get_inactive_workers(
                    session, threshold_minutes=config.WORKER_INACTIVE_THRESHOLD_MINUTES
                )
                for worker_id in inactive_workers:
                    logging.warning(
                        f"Worker {worker_id} inactive for over {config.WORKER_INACTIVE_THRESHOLD_MINUTES} min."
                    )
                    notify_inactive_worker(worker_id, config.WORKER_INACTIVE_THRESHOLD_MINUTES)

                # --- Reconcile DB and Redis queue ---
                reconcile_db_redis(session, r)

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