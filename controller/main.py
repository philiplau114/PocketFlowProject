import time
import logging
import redis
import json
import signal
import os
from pathlib import Path
from datetime import datetime
import shutil

import config  # Only import config, not individual constants!

from dotenv import load_dotenv
from sqlalchemy import or_, and_
from db_utils import get_db, update_job_status, job_has_success
from db.db_models import ControllerTask
from db.status_constants import (
    STATUS_NEW, STATUS_QUEUED, STATUS_WORKER_COMPLETED, STATUS_WORKER_FAILED,
    STATUS_RETRYING, STATUS_FINE_TUNING, STATUS_COMPLETED_SUCCESS,
    STATUS_COMPLETED_PARTIAL, STATUS_FAILED
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKER_DIR = os.path.join(PROJECT_ROOT, 'controller')

load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=False)
load_dotenv(os.path.join(WORKER_DIR, '.env.controller'), override=True)

from notify import send_email, send_telegram
from controller.controller_utils import (
    get_task_metric_scores,
    spawn_fine_tune_task,
    queue_task_to_redis
)
from db_utils import extract_setfile_metadata, insert_job_and_task

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
    retry_bump = 2 ** (task.attempt_count or 0) if task.status == STATUS_RETRYING else 0
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60) if (task.updated_at or task.created_at) else 0
    aging = config.AGING_FACTOR * age_minutes
    return base + retry_bump + aging

def mark_task_failed(session, task, reason=None):
    task.status = STATUS_FAILED
    task.last_error = reason
    session.commit()
    update_job_status(session, task.job_id)
    subject = f"Task Failed: {task.file_path or task.id}"
    body = f"Task {task.id} marked as failed.\nReason: {reason or 'Unknown'}."
    send_email(subject, body)
    send_telegram(body)

def mark_task_success(session, task):
    task.status = STATUS_COMPLETED_SUCCESS
    session.commit()
    update_job_status(session, task.job_id)
    logging.info(f"Task {task.id} marked as {STATUS_COMPLETED_SUCCESS}.")

def mark_task_partial(session, task):
    task.status = STATUS_COMPLETED_PARTIAL
    session.commit()
    update_job_status(session, task.job_id)
    logging.info(f"Task {task.id} marked as {STATUS_COMPLETED_PARTIAL}.")

def hybrid_priority(task, now=None):
    now = now or datetime.utcnow()
    base = task.priority or 10
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60) if (task.updated_at or task.created_at) else 0
    aging = config.AGING_FACTOR * age_minutes
    if getattr(task, "status", None) == STATUS_RETRYING:
        return (base * (2 ** (task.attempt_count or 1))) + aging
    elif getattr(task, "step_name", None) == "fine_tune" and hasattr(task, "_distance") and task._distance is not None:
        return (1000 - int(task._distance * 100)) + aging
    else:
        return base + aging

def mark_task_retrying(session, task):
    if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
        task.status = STATUS_RETRYING
        task.updated_at = datetime.utcnow()
        session.commit()
        update_job_status(session, task.job_id)
        logging.info(f"Task {task.id} marked as {STATUS_RETRYING}.")

def main_loop():
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=False)
    POLL_INTERVAL = 20  # seconds

    BATCH_SIZE = 10
    MIN_NEW = 2

    last_reload = time.time()

    while not stop_flag:
        now = time.time()
        if now - last_reload > config.RELOAD_INTERVAL:
            thresholds_db = config.load_thresholds_from_db()
            config.TASK_MAX_ATTEMPTS = int(thresholds_db.get('MAX_ATTEMPTS', config.TASK_MAX_ATTEMPTS))
            config.MAX_FINE_TUNE_DEPTH = int(thresholds_db.get('MAX_FINE_TUNE_DEPTH', config.MAX_FINE_TUNE_DEPTH))
            config.DISTANCE_THRESHOLD = float(thresholds_db.get('DISTANCE_THRESHOLD', config.DISTANCE_THRESHOLD))
            config.SCORE_THRESHOLD = float(thresholds_db.get('SCORE_THRESHOLD', config.SCORE_THRESHOLD))
            config.AGING_FACTOR = float(thresholds_db.get('AGING_FACTOR', config.AGING_FACTOR))
            last_reload = now

        # --- WATCH_FOLDER LOGIC ---
        for file in Path(config.WATCH_FOLDER).glob("*.set"):
            try:
                print(f"DEBUG: Processing file: {file}")
                meta = extract_setfile_metadata(str(file))
                print(f"DEBUG: Metadata extracted: {meta}")
                with get_db() as session:
                    job_id, task_id, is_new = insert_job_and_task(session, meta, str(file), user_id=config.USER_ID)
                    print(f"DEBUG: job_id={job_id}, task_id={task_id}, is_new={is_new}")
                    if not is_new:
                        print(f"DEBUG: Skipping {file} as job/task already exists.")
                        continue
                    with open(file, "rb") as f:
                        file_blob = f.read()
                    print(f"DEBUG: Read file blob ({len(file_blob)} bytes)")
                    task = session.query(ControllerTask).get(task_id)
                    print(f"DEBUG: Task fetched: {task}")
                    task.file_blob = file_blob
                    # DO NOT set status to 'queued' here; keep as STATUS_NEW
                    session.commit()
                    print("DEBUG: file_blob committed to DB")
                shutil.move(str(file), str(config.PROCESSED_FOLDER / file.name))
                logging.info(f"Moved processed file {file.name} to {config.PROCESSED_FOLDER}")
                print(f"DEBUG: Task for file {file.name} processed and ready for queueing.")
                logging.info("Created new task: %s (using file_blob)", file.name)
            except Exception as e:
                error_msg = f"Failed to process file {file.name}: {e}"
                print(f"EXCEPTION: {error_msg}")
                logging.error(error_msg)
                subject = f"Task File Processing Failed: {file.name}"
                body = f"{error_msg}\n\nPlease check the file and system logs."
                send_email(subject, body)
                send_telegram(body)

        # --- POST-WORKER STATUS HANDLING ---
        try:
            with get_db() as session:
                finished_tasks = session.query(ControllerTask).filter(
                    ControllerTask.status.in_([STATUS_WORKER_COMPLETED, STATUS_WORKER_FAILED])
                ).all()
                for task in finished_tasks:
                    if job_has_success(session, task.job_id):
                        logging.info(
                            f"Job {task.job_id} already has a successful task. Skipping retry/fine-tune for task {task.id}.")
                        continue

                    if task.status == STATUS_WORKER_COMPLETED:
                        task_ids = [task.id]
                        metrics_map = get_task_metric_scores(session, task_ids)
                        m = metrics_map.get(task.id, {})
                        task._distance = m.get('distance')
                        task._score = m.get('score')
                        if (task._distance is not None and task._distance <= config.DISTANCE_THRESHOLD) and \
                           (task._score is not None and task._score >= config.SCORE_THRESHOLD):
                            mark_task_success(session, task)
                        elif (task._distance is not None and task._distance <= config.DISTANCE_THRESHOLD) or \
                             (task._score is not None and task._score >= config.SCORE_THRESHOLD):
                            mark_task_partial(session, task)
                            if (task.fine_tune_depth or 0) < config.MAX_FINE_TUNE_DEPTH:
                                child = spawn_fine_tune_task(session, task)
                                queue_task_to_redis(r, child)
                        else:
                            if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
                                mark_task_retrying(session, task)
                            else:
                                mark_task_failed(session, task, reason="Max attempts reached after worker_completed")
                        session.commit()
                        update_job_status(session, task.job_id)
                    elif task.status == STATUS_WORKER_FAILED:
                        if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
                            mark_task_retrying(session, task)
                        else:
                            mark_task_failed(session, task, reason="Worker failure and max attempts reached")
                        session.commit()
                        update_job_status(session, task.job_id)

        except Exception as ex:
            logging.error(f"Error in post-worker status handling: {ex}")

        # --- CONTROLLER LOGIC (fine-tune, retry, queueing) ---
        try:
            with get_db() as session:
                now = datetime.utcnow()
                eligible_status = [STATUS_NEW, STATUS_RETRYING, STATUS_FINE_TUNING]
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

                queueable_status = [STATUS_NEW, STATUS_RETRYING, STATUS_FINE_TUNING]
                queueable = [
                    t for t in scored_tasks
                    if t.status in queueable_status
                    and (t.attempt_count or 0) < (t.max_attempts or config.TASK_MAX_ATTEMPTS)
                    and (t.fine_tune_depth or 0) <= config.MAX_FINE_TUNE_DEPTH
                    and not job_has_success(session, t.job_id)  # <-- add this line
                ]

                print(f"DEBUG: Found {len(queueable)} queueable tasks")
                new_tasks = [t for t in queueable if t.status == STATUS_NEW]
                other_tasks = [t for t in queueable if t.status != STATUS_NEW]

                new_tasks = sorted(new_tasks, key=lambda t: t._priority, reverse=True)
                other_tasks = sorted(other_tasks, key=lambda t: t._priority, reverse=True)

                batch = new_tasks[:MIN_NEW]
                fill_count = BATCH_SIZE - len(batch)
                batch += other_tasks[:fill_count]

                print(f"DEBUG: Batch to queue (length={len(batch)}): {[t.id for t in batch]}")
                for task in batch:
                    print(f"DEBUG: Preparing to queue task id={task.id}, type={type(task.id)}, job_id={task.job_id}, type(job_id)={type(task.job_id)}")
                    old_status = task.status
                    task.status = STATUS_QUEUED
                    task.updated_at = datetime.utcnow()
                    if old_status == STATUS_RETRYING:
                        task.attempt_count = (task.attempt_count or 0) + 1
                    session.commit()
                    update_job_status(session, task.job_id)
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