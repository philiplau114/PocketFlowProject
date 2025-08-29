import time
import logging
from db_utils import get_db, get_stuck_tasks, requeue_task, get_inactive_workers
from notify import send_email, send_telegram
import config  # <--- Import your config.py

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

def main():
    while True:
        try:
            with get_db() as session:
                # --- Handle Stuck Tasks ---
                stuck_tasks = get_stuck_tasks(session, threshold_minutes=config.JOB_STUCK_THRESHOLD_MINUTES)
                for task in stuck_tasks:
                    notify_stuck_task(task)
                    current_attempt = (task.attempt_count or 0)
                    max_attempts = task.max_attempts or 1
                    if current_attempt + 1 < max_attempts:
                        requeue_task(session, task)
                        logging.warning(f"Task {task.id} ({task.file_path}) stuck for over {config.JOB_STUCK_THRESHOLD_MINUTES} min. Retrying (attempt {current_attempt + 1}/{max_attempts}).")
                        notify_task_retry(task, current_attempt)
                    else:
                        task.status = "failed"
                        session.commit()
                        logging.warning(f"Task {task.id} ({task.file_path}) permanently failed after {max_attempts} attempts.")
                        notify_task_failed(task)

                # --- Handle Inactive Workers ---
                inactive_workers = get_inactive_workers(session, threshold_minutes=config.WORKER_INACTIVE_THRESHOLD_MINUTES)
                for worker_id in inactive_workers:
                    logging.warning(f"Worker {worker_id} inactive for over {config.WORKER_INACTIVE_THRESHOLD_MINUTES} min.")
                    notify_inactive_worker(worker_id, config.WORKER_INACTIVE_THRESHOLD_MINUTES)

        except Exception as e:
            logging.error("Supervisor error: %s", e)
            subject = "[Supervisor Error]"
            body = f"Supervisor encountered an error: {e}"
            send_email(subject, body)
            send_telegram(body)

        time.sleep(config.SUPERVISOR_POLL_INTERVAL)

if __name__ == "__main__":
    main()