import time
import logging
import redis
import json
import signal
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import or_, and_
from db_utils import get_db
from db.db_models import ControllerTask
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_QUEUE, WATCH_FOLDER, USER_ID,
    TASK_MAX_ATTEMPTS, MAX_FINE_TUNE_DEPTH,
    DISTANCE_THRESHOLD, SCORE_THRESHOLD, AGING_FACTOR,
)
from notify import send_email, send_telegram
from controller_utils import (
    get_task_metric_scores,
    spawn_fine_tune_task,
    queue_task_to_redis
)
from db_utils import extract_setfile_metadata
from db_utils import insert_job_and_task

logging.basicConfig(level=logging.INFO)

stop_flag = False

def handle_stop_signal(sig, frame):
    global stop_flag
    logging.info("Received stop signal, will exit after this iteration.")
    stop_flag = True

signal.signal(signal.SIGINT, handle_stop_signal)
signal.signal(signal.SIGTERM, handle_stop_signal)

def effective_priority(task, now=None):
    now = now or datetime.utcnow()
    base = task.priority or 0
    retry_bump = 2 ** (task.attempt_count or 0) if task.status == 'retrying' else 0
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60) if (task.updated_at or task.created_at) else 0
    aging = AGING_FACTOR * age_minutes
    return base + retry_bump + aging

def mark_task_failed(session, task, reason=None):
    task.status = 'failed'
    task.last_error = reason
    session.commit()
    subject = f"Task Failed: {task.file_path or task.id}"
    body = f"Task {task.id} marked as failed.\nReason: {reason or 'Unknown'}."
    send_email(subject, body)
    send_telegram(body)

def mark_task_success(session, task):
    task.status = 'completed_success'
    session.commit()
    logging.info(f"Task {task.id} marked as completed_success.")

def mark_task_partial(session, task):
    task.status = 'completed_partial'
    session.commit()
    logging.info(f"Task {task.id} marked as completed_partial.")

def hybrid_priority(task, now=None):
    now = now or datetime.utcnow()
    base = task.priority or 10
    # Aging (optional)
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60) if (task.updated_at or task.created_at) else 0
    aging = AGING_FACTOR * age_minutes

    # Exponential bump for retries
    if getattr(task, "status", None) == "retrying":
        return (base * (2 ** (task.attempt_count or 1))) + aging
    # Metric-based for fine-tune children
    elif getattr(task, "step_name", None) == "fine_tune" and hasattr(task, "_distance") and task._distance is not None:
        return (1000 - int(task._distance * 100)) + aging
    # Default case
    else:
        return base + aging

def main_loop():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    POLL_INTERVAL = 20  # seconds

    BATCH_SIZE = 10
    MIN_NEW = 2

    processed_files = set()

    while not stop_flag:
        # --- WATCH_FOLDER LOGIC ---
        for file in Path(WATCH_FOLDER).glob("*.set"):
            if file.name in processed_files:
                continue
            try:
                meta = extract_setfile_metadata(str(file))
                with get_db() as session:
                    job_id, task_id = insert_job_and_task(session, meta, str(file), user_id=USER_ID)
                    # Read the file blob
                    with open(file, "rb") as f:
                        file_blob = f.read()
                    # Update ControllerTask with file_blob
                    task = session.query(ControllerTask).get(task_id)
                    task.file_blob = file_blob
                    session.commit()
                # The rest is handled in queue_task_to_redis
                processed_files.add(file.name)
                logging.info("Queued new task: %s (using file_blob)", file.name)
            except Exception as e:
                error_msg = f"Failed to process file {file.name}: {e}"
                logging.error(error_msg)
                subject = f"Task File Processing Failed: {file.name}"
                body = f"{error_msg}\n\nPlease check the file and system logs."
                send_email(subject, body)
                send_telegram(body)

        # --- CONTROLLER LOGIC (fine-tune, retry, etc) ---
        try:
            with get_db() as session:
                now = datetime.utcnow()
                eligible_status = ['new', 'retrying', 'fine_tuning', 'queued']
                tasks = session.query(ControllerTask).filter(
                    ControllerTask.status.in_(eligible_status)
                ).all()
                if not tasks:
                    logging.info("No tasks eligible for queueing.")
                    time.sleep(POLL_INTERVAL)
                    continue

                task_ids = [t.id for t in tasks]
                metrics_map = get_task_metric_scores(session, task_ids)

                scored_tasks = []
                for t in tasks:
                    m = metrics_map.get(t.id, {})
                    t._distance = m.get('distance')
                    t._score = m.get('score')
                    t._priority = hybrid_priority(t)
                    scored_tasks.append(t)

                for task in scored_tasks:
                    if (task.attempt_count or 0) >= (task.max_attempts or TASK_MAX_ATTEMPTS):
                        mark_task_failed(session, task, reason="Max attempts reached")
                        continue
                    if (task.fine_tune_depth or 0) > MAX_FINE_TUNE_DEPTH:
                        mark_task_failed(session, task, reason="Max fine-tune depth reached")
                        continue
                    if (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) and \
                       (task._score is not None and task._score >= SCORE_THRESHOLD):
                        mark_task_success(session, task)
                        continue
                    if (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) or \
                       (task._score is not None and task._score >= SCORE_THRESHOLD):
                        mark_task_partial(session, task)
                        if (task.fine_tune_depth or 0) < MAX_FINE_TUNE_DEPTH:
                            child = spawn_fine_tune_task(session, task)
                            queue_task_to_redis(r, child)
                        continue

                queueable_status = ['new', 'retrying', 'fine_tuning', 'queued']
                queueable = [
                    t for t in scored_tasks
                    if t.status in queueable_status
                    and (t.attempt_count or 0) < (t.max_attempts or TASK_MAX_ATTEMPTS)
                    and (t.fine_tune_depth or 0) <= MAX_FINE_TUNE_DEPTH
                ]

                new_tasks = [t for t in queueable if t.status == 'new']
                other_tasks = [t for t in queueable if t.status != 'new']

                new_tasks = sorted(new_tasks, key=lambda t: t._priority, reverse=True)
                other_tasks = sorted(other_tasks, key=lambda t: t._priority, reverse=True)

                batch = new_tasks[:MIN_NEW]
                fill_count = BATCH_SIZE - len(batch)
                batch += other_tasks[:fill_count]

                for task in batch:
                    old_status = task.status
                    task.status = 'queued'
                    task.updated_at = datetime.utcnow()
                    if old_status == 'retrying':
                        task.attempt_count = (task.attempt_count or 0) + 1
                    session.commit()
                    queue_task_to_redis(r, task)

            time.sleep(POLL_INTERVAL)
        except Exception as e:
            logging.error(f"Controller main loop error: {e}")
            subject = "[Controller Error]"
            body = f"Controller encountered an error: {e}"
            send_email(subject, body)
            send_telegram(body)
            time.sleep(POLL_INTERVAL)

    logging.info("Controller stopped gracefully.")

if __name__ == "__main__":
    main_loop()