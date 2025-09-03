import time
import logging
import redis
import json
import signal
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import or_, and_
from db_utils import get_db
from db.db_models import ControllerTask

# Load .env.worker first for overrides, then .env for defaults
# Get the absolute path to the project root and worker folder
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKER_DIR = os.path.join(PROJECT_ROOT, 'controller')

# Load .env from the root
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=False)

# Load .env.worker from the worker directory
load_dotenv(os.path.join(WORKER_DIR, '../controller/.env.controller'), override=True)

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_QUEUE, WATCH_FOLDER, USER_ID,
    TASK_MAX_ATTEMPTS, MAX_FINE_TUNE_DEPTH,
    DISTANCE_THRESHOLD, SCORE_THRESHOLD, AGING_FACTOR,
)
from notify import send_email, send_telegram
from controller.controller_utils import (
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
                print(f"DEBUG: Processing file: {file}")
                meta = extract_setfile_metadata(str(file))
                print(f"DEBUG: Metadata extracted: {meta}")
                with get_db() as session:
                    job_id, task_id, is_new = insert_job_and_task(session, meta, str(file), user_id=USER_ID)
                    print(f"DEBUG: job_id={job_id}, task_id={task_id}, is_new={is_new}")
                    if not is_new:
                        print(f"DEBUG: Skipping {file} as job/task already exists.")
                        continue
                    # Read the file blob
                    with open(file, "rb") as f:
                        file_blob = f.read()
                    print(f"DEBUG: Read file blob ({len(file_blob)} bytes)")
                    # Update ControllerTask with file_blob
                    task = session.query(ControllerTask).get(task_id)
                    print(f"DEBUG: Task fetched: {task}")
                    task.file_blob = file_blob
                    session.commit()
                    print("DEBUG: file_blob committed to DB")
                processed_files.add(file.name)
                print(f"DEBUG: Task for file {file.name} processed and queued.")
                logging.info("Queued new task: %s (using file_blob)", file.name)
            except Exception as e:
                error_msg = f"Failed to process file {file.name}: {e}"
                print(f"EXCEPTION: {error_msg}")
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
                print(f"DEBUG: Querying tasks with eligible_status={eligible_status}")
                tasks = session.query(ControllerTask).filter(
                    ControllerTask.status.in_(eligible_status)
                ).all()
                print(f"DEBUG: Retrieved {len(tasks)} eligible tasks")
                if not tasks:
                    logging.info("No tasks eligible for queueing.")
                    time.sleep(POLL_INTERVAL)
                    continue

                task_ids = [t.id for t in tasks]
                print(f"DEBUG: task_ids: {task_ids} (types: {[type(ti) for ti in task_ids]})")
                metrics_map = get_task_metric_scores(session, task_ids)
                print(f"DEBUG: metrics_map: {metrics_map}")

                scored_tasks = []
                for t in tasks:
                    print(f"DEBUG: Scoring task id={t.id} (type={type(t.id)})")
                    m = metrics_map.get(t.id, {})
                    t._distance = m.get('distance')
                    t._score = m.get('score')
                    t._priority = hybrid_priority(t)
                    print(f"DEBUG: Task {t.id} scored: distance={t._distance}, score={t._score}, priority={t._priority}")
                    scored_tasks.append(t)

                for task in scored_tasks:
                    print(f"DEBUG: Checking task id={task.id}, status={task.status}, attempt_count={task.attempt_count}, fine_tune_depth={getattr(task, 'fine_tune_depth', None)}")
                    if (task.attempt_count or 0) >= (task.max_attempts or TASK_MAX_ATTEMPTS):
                        print(f"DEBUG: Marking task {task.id} as failed (max attempts reached)")
                        mark_task_failed(session, task, reason="Max attempts reached")
                        continue
                    if (task.fine_tune_depth or 0) > MAX_FINE_TUNE_DEPTH:
                        print(f"DEBUG: Marking task {task.id} as failed (max fine-tune depth reached)")
                        mark_task_failed(session, task, reason="Max fine-tune depth reached")
                        continue
                    if (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) and \
                       (task._score is not None and task._score >= SCORE_THRESHOLD):
                        print(f"DEBUG: Marking task {task.id} as completed_success (distance and score thresholds met)")
                        mark_task_success(session, task)
                        continue
                    if (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) or \
                       (task._score is not None and task._score >= SCORE_THRESHOLD):
                        print(f"DEBUG: Marking task {task.id} as completed_partial (one threshold met)")
                        mark_task_partial(session, task)
                        if (task.fine_tune_depth or 0) < MAX_FINE_TUNE_DEPTH:
                            print(f"DEBUG: Spawning fine-tune child for task {task.id}")
                            child = spawn_fine_tune_task(session, task)
                            print(f"DEBUG: Queuing fine-tune child task id={child.id}, job_id={child.job_id}, type(child.id)={type(child.id)}, type(child.job_id)={type(child.job_id)}")
                            queue_task_to_redis(r, child)
                        continue

                queueable_status = ['new', 'retrying', 'fine_tuning', 'queued']
                queueable = [
                    t for t in scored_tasks
                    if t.status in queueable_status
                    and (t.attempt_count or 0) < (t.max_attempts or TASK_MAX_ATTEMPTS)
                    and (t.fine_tune_depth or 0) <= MAX_FINE_TUNE_DEPTH
                ]

                print(f"DEBUG: Found {len(queueable)} queueable tasks")
                new_tasks = [t for t in queueable if t.status == 'new']
                other_tasks = [t for t in queueable if t.status != 'new']

                new_tasks = sorted(new_tasks, key=lambda t: t._priority, reverse=True)
                other_tasks = sorted(other_tasks, key=lambda t: t._priority, reverse=True)

                batch = new_tasks[:MIN_NEW]
                fill_count = BATCH_SIZE - len(batch)
                batch += other_tasks[:fill_count]

                print(f"DEBUG: Batch to queue (length={len(batch)}): {[t.id for t in batch]}")
                for task in batch:
                    print(f"DEBUG: Preparing to queue task id={task.id}, type={type(task.id)}, job_id={task.job_id}, type(job_id)={type(task.job_id)}")
                    old_status = task.status
                    task.status = 'queued'
                    task.updated_at = datetime.utcnow()
                    if old_status == 'retrying':
                        task.attempt_count = (task.attempt_count or 0) + 1
                    session.commit()
                    print(f"DEBUG: Committed task id={task.id}, now queuing to Redis")
                    queue_task_to_redis(r, task)
                    print(f"DEBUG: Queued task id={task.id} to Redis")

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