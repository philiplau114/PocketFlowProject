import time
import logging
import redis
import json

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

def handle_processing_queue_stuck_tasks(r, session):
    # Scan processing queue for stuck tasks and retry/dead-letter as needed
    processing_queue = config.REDIS_PROCESSING_QUEUE
    stuck_threshold = config.JOB_STUCK_THRESHOLD_MINUTES * 60  # seconds
    processing_tasks = r.lrange(processing_queue, 0, -1)
    now = time.time()

    for task_json in processing_tasks:
        try:
            if isinstance(task_json, bytes):
                task_json = task_json.decode("utf-8")
            task = json.loads(task_json)
            task_id = task.get("task_id")
            controller_task = session.query(ControllerTask).get(task_id)
            if not controller_task:
                continue
            started_at = getattr(controller_task, "updated_at", None)
            if started_at:
                seconds_in_processing = (now - started_at.timestamp())
            else:
                seconds_in_processing = stuck_threshold + 1

            if seconds_in_processing > stuck_threshold:
                logging.warning(f"Task {task_id} stuck in processing queue for {seconds_in_processing}s")
                current_attempt = controller_task.attempt_count or 0
                max_attempts = controller_task.max_attempts or 1

                if current_attempt + 1 < max_attempts:
                    r.lrem(processing_queue, 1, task_json)
                    r.lpush(config.REDIS_MAIN_QUEUE, task_json)
                    requeue_task(session, controller_task)
                    notify_task_retry(controller_task, current_attempt)
                else:
                    r.lrem(processing_queue, 1, task_json)
                    r.lpush(config.REDIS_DEAD_LETTER_QUEUE, task_json)
                    controller_task.status = "failed"
                    session.commit()
                    notify_task_failed(controller_task)
        except Exception as e:
            logging.error(f"Error handling stuck processing task: {e}")

def reconcile_db_redis(session, r, redis_main_queue):
    # Requeue any 'queued' tasks in DB but missing from Redis main/processing queues
    logging.info("Reconciling DB and Redis queue for 'queued' tasks...")

    main_queue_tasks = set(r.lrange(config.REDIS_MAIN_QUEUE, 0, -1))
    processing_queue_tasks = set(r.lrange(config.REDIS_PROCESSING_QUEUE, 0, -1))

    tasks = session.query(ControllerTask).filter_by(status="queued").all()
    requeued_count = 0
    for task in tasks:
        task_data = {
            "job_id": task.job_id,
            "task_id": task.id,
            "set_file_name": task.file_path,
            "ea_name": getattr(task, 'ea_name', None),
            "symbol": getattr(task, 'symbol', None),
            "timeframe": getattr(task, 'timeframe', None),
        }
        task_json = json.dumps(task_data)
        if (task_json not in main_queue_tasks) and (task_json not in processing_queue_tasks):
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
                    notify_stuck_task(task)
                    current_attempt = (task.attempt_count or 0)
                    max_attempts = task.max_attempts or 1
                    if current_attempt + 1 < max_attempts:
                        requeue_task(session, task)
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) stuck for over {config.JOB_STUCK_THRESHOLD_MINUTES} min. Retrying (attempt {current_attempt + 1}/{max_attempts})."
                        )
                        notify_task_retry(task, current_attempt)
                    else:
                        task.status = "failed"
                        session.commit()
                        logging.warning(
                            f"Task {task.id} ({task.file_path}) permanently failed after {max_attempts} attempts."
                        )
                        notify_task_failed(task)

                # --- Handle Stuck Tasks in Processing Queue ---
                handle_processing_queue_stuck_tasks(r, session)

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
                reconcile_db_redis(session, r, config.REDIS_MAIN_QUEUE)

        except Exception as e:
            logging.error("Supervisor error: %s", e)
            subject = "[Supervisor Error]"
            body = f"Supervisor encountered an error: {e}"
            send_email(subject, body)
            send_telegram(body)

        time.sleep(config.SUPERVISOR_POLL_INTERVAL)

if __name__ == "__main__":
    main()