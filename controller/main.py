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
#                                    +-------------------+
#                                    |    STATUS_NEW     |
#                                    +-------------------+
#                                              |
#                                              v
#                                    +--------------------+
#                                    |   STATUS_QUEUED    |   (queued by controller)
#                                    +--------------------+
#                                              |
#                                              v
#                                    +-----------------------------+
#                                    | STATUS_WORKER_IN_PROGRESS   |  (worker picks up)
#                                    +-----------------------------+
#                                              |
#                       +----------------------+---------------------+
#                       |                                            |
#                       v                                            v
#          +-----------------------------+            +-----------------------------+
#          | STATUS_WORKER_COMPLETED      |            | STATUS_WORKER_FAILED        |
#          +-----------------------------+            +-----------------------------+
#                       |                                            |
#          +------------+------------+                    +----------+-----------+
#          |                         |                    |                      |
#          v                         v                    v                      v
# +-------------------+   +------------------------+   +-------------------+   +-------------------+
# |  All metrics      |   |  At least one metric   |   | Retry attempts    |   | Max attempts or   |
# |  passed (success) |   |  passed (partial)      |   | remain            |   | no attempts left  |
# +-------------------+   +------------------------+   +-------------------+   +-------------------+
#         |                        |                         |                      |
#         v                        v                         v                      v
# +---------------------+   +--------------------------+   +------------------+   +-------------------------+
# | STATUS_COMPLETED_   |   | STATUS_COMPLETED_PARTIAL |   | STATUS_RETRYING  |   | STATUS_FAILED           |
# | SUCCESS             |   +--------------------------+   +------------------+   +-------------------------+
# +---------------------+            |                                          (terminal)
#          |                        (controller checks periodically)
#          |                                 |
#          |                                 v
#          |                 [If not at fine-tune depth limit and no child exists:]
#          |                                 |
#          |                    +------------------------------+
#          |                    |  Spawn fine-tune child task  |
#          |                    +------------------------------+
#          |                                 |
#          |                                 v
#          |                    +--------------------------+
#          |                    |  STATUS_FINE_TUNING      |
#          |                    +--------------------------+
#          |                                 |
#          |                    (same path as new task: queued, worker, etc.)
#          +-----------------------------+---+-----------------------------------+

# --- Signal Handling for Graceful Shutdown ---
def handle_stop_signal(sig, frame):
    global stop_flag
    logging.info("Received stop signal, will exit after this iteration.")
    stop_flag = True

signal.signal(signal.SIGINT, handle_stop_signal)
signal.signal(signal.SIGTERM, handle_stop_signal)

# --- Utility Functions for Priority and Status Management ---
def effective_priority(task, now=None):
    """
    Compute the effective priority of a task for queueing, including base priority,
    retry boost, and aging bonus.
    """
    now = now or datetime.utcnow()
    base = task.priority or 0
    retry_bump = 2 ** (task.attempt_count or 0) if task.status == STATUS_RETRYING else 0
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60) if (task.updated_at or task.created_at) else 0
    aging = config.AGING_FACTOR * age_minutes
    return base + retry_bump + aging

def hybrid_priority(task, now=None):
    """
    Compute a hybrid priority, including special handling for retrying and fine-tune tasks.
    """
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

def handle_terminal_task(r, task):
    """
    Handles cleanup for tasks reaching terminal status.
    - Deletes file_blob from Redis.
    - No queue cleanup needed (worker already removes from queue).
    """
    if hasattr(task, "input_blob_key") and task.input_blob_key:
        try:
            r.delete(task.input_blob_key)
            logging.info(f"Deleted file_blob {task.input_blob_key} for completed/failed task {task.id}")
        except Exception as e:
            logging.warning(f"Failed to delete file_blob {task.input_blob_key} for task {task.id}: {e}")

def mark_task_failed(session, task, reason=None):
    """
    Mark a task as failed with optional reason and update job status.
    """
    task.status = STATUS_FAILED
    task.last_error = reason
    session.commit()
    update_job_status(session, task.job_id)
    subject = f"Task Failed: {task.file_path or task.id}"
    body = f"Task {task.id} marked as failed.\nReason: {reason or 'Unknown'}."
    send_email(subject, body)
    send_telegram(body)

def mark_task_success(session, task):
    """
    Mark a task as completed successfully and update job status.
    """
    task.status = STATUS_COMPLETED_SUCCESS
    session.commit()
    update_job_status(session, task.job_id)
    logging.info(f"Task {task.id} marked as {STATUS_COMPLETED_SUCCESS}.")

def mark_task_partial(session, task):
    """
    Mark a task as completed partial (some metrics pass) and update job status.
    Fine-tune spawning is controller-managed and handled separately.
    """
    task.status = STATUS_COMPLETED_PARTIAL
    session.commit()
    update_job_status(session, task.job_id)
    logging.info(f"Task {task.id} marked as {STATUS_COMPLETED_PARTIAL}.")

def mark_task_retrying(session, task):
    """
    Mark a task as retrying (not yet reached max attempts), update job status.
    """
    if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
        task.status = STATUS_RETRYING
        task.updated_at = datetime.utcnow()
        session.commit()
        update_job_status(session, task.job_id)
        logging.info(f"Task {task.id} marked as {STATUS_RETRYING}.")

# --- Fine-tune Logic for Partial Tasks ---
def handle_partial_tasks(session):
    logging.info("handle_partial_tasks: starting")
    partial_tasks = session.query(ControllerTask).filter(
        ControllerTask.status == STATUS_COMPLETED_PARTIAL
    ).all()
    logging.info(f"handle_partial_tasks: found {len(partial_tasks)} partial tasks")
    for task in partial_tasks:
        logging.info(f"handle_partial_tasks: checking partial task {task.id}, fine_tune_depth={task.fine_tune_depth}")
        exists = session.query(ControllerTask).filter_by(
            parent_task_id=task.id, step_name='fine_tune'
        ).count() > 0
        logging.info(f"handle_partial_tasks: fine-tune child exists for {task.id}? {exists}")
        if not exists and (task.fine_tune_depth or 0) < config.MAX_FINE_TUNE_DEPTH:
            try:
                logging.info(f"handle_partial_tasks: spawning fine-tune for {task.id}")
                ft_task = spawn_fine_tune_task(session, task)
                logging.info(f"handle_partial_tasks: spawned fine-tune task {ft_task.id} for parent {task.id}")
            except Exception as e:
                logging.error(f"Could not spawn fine-tune task for {task.id}: {e}")

# --- Main Controller Loop ---
def main_loop():
    """
    Main controller loop:
    - Watches for new tasks (from file drop).
    - Handles post-worker status transitions and retry/fine-tune logic.
    - Periodically checks partial tasks to spawn fine-tune children if needed.
    - Queues eligible tasks to Redis for worker processing.
    """
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=False)
    POLL_INTERVAL = 20  # seconds

    BATCH_SIZE = 10
    MIN_NEW = 2

    last_reload = time.time()

    while not stop_flag:
        now = time.time()
        # --- Reload thresholds/config from DB if needed ---
        if now - last_reload > config.RELOAD_INTERVAL:
            thresholds_db = config.load_thresholds_from_db()
            config.TASK_MAX_ATTEMPTS = int(thresholds_db.get('MAX_ATTEMPTS', config.TASK_MAX_ATTEMPTS))
            config.MAX_FINE_TUNE_DEPTH = int(thresholds_db.get('MAX_FINE_TUNE_DEPTH', config.MAX_FINE_TUNE_DEPTH))
            config.DISTANCE_THRESHOLD = float(thresholds_db.get('DISTANCE_THRESHOLD', config.DISTANCE_THRESHOLD))
            config.SCORE_THRESHOLD = float(thresholds_db.get('SCORE_THRESHOLD', config.SCORE_THRESHOLD))
            config.AGING_FACTOR = float(thresholds_db.get('AGING_FACTOR', config.AGING_FACTOR))
            last_reload = now

        # --- WATCH_FOLDER LOGIC: Create new tasks from .set files ---
        for file in Path(config.WATCH_FOLDER).glob("*.set"):
            try:
                logging.debug(f"Processing file: {file}")
                meta_path = str(file) + ".meta.json"
                meta_data = None
                user_id = config.USER_ID  # default fallback

                # Try to load task metadata from .meta.json if present
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_json = json.load(f)
                    user_id = meta_json.get("user_id", config.USER_ID)
                    meta_data = {k: meta_json[k] for k in ["symbol", "timeframe", "ea_name", "original_filename"] if k in meta_json}
                    logging.debug(f"Loaded metadata from {meta_path}: {meta_data} with user_id={user_id}")
                else:
                    # Fallback: extract metadata from .set file (legacy)
                    meta_data = extract_setfile_metadata(str(file))
                    logging.debug(f"Metadata extracted from .set file: {meta_data}")

                # Add job/task to DB if not exists and store file_blob
                with get_db() as session:
                    job_id, task_id, is_new = insert_job_and_task(session, meta_data, str(file), user_id=user_id)
                    logging.debug(f"job_id={job_id}, task_id={task_id}, is_new={is_new}")
                    if not is_new:
                        logging.debug(f"Skipping {file} as job/task already exists.")
                        continue
                    with open(file, "rb") as f:
                        file_blob = f.read()
                    logging.debug(f"Read file blob ({len(file_blob)} bytes)")
                    task = session.query(ControllerTask).get(task_id)
                    logging.debug(f"Task fetched: {task}")
                    task.file_blob = file_blob
                    session.commit()
                    print("DEBUG: file_blob committed to DB")
                # Move processed files to processed folder
                shutil.move(str(file), os.path.join(config.PROCESSED_FOLDER, file.name))
                if os.path.exists(meta_path):
                    shutil.move(meta_path, os.path.join(config.PROCESSED_FOLDER, os.path.basename(meta_path)))
                logging.info(f"Moved processed file {file.name} and meta to {config.PROCESSED_FOLDER}")
                logging.debug(f"Task for file {file.name} processed and ready for queueing.")
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
        # After worker completes a task, controller evaluates metrics and determines next step.
        try:
            with get_db() as session:
                finished_tasks = session.query(ControllerTask).filter(
                    ControllerTask.status.in_([STATUS_WORKER_COMPLETED, STATUS_WORKER_FAILED])
                ).all()
                for task in finished_tasks:
                    # If job already succeeded, skip further transitions for this task.
                    if job_has_success(session, task.job_id):
                        logging.info(
                            f"Job {task.job_id} already has a successful task. Skipping retry/fine-tune for task {task.id}.")
                        continue

                    terminal_status = False

                    if task.status == STATUS_WORKER_COMPLETED:
                        # Evaluate metrics for this task
                        metrics_map = get_task_metric_scores(session, [task.id])
                        metrics = metrics_map.get(task.id, [])
                        if not isinstance(metrics, list):
                            metrics = [metrics]
                        success = False
                        partial = False

                        for m in metrics:
                            score = m.get('score')
                            distance = m.get('distance')
                            logging.info(f"Task {task.id} metric: score={score}, distance={distance}")
                            # Success: any metric meets BOTH thresholds
                            if (score is not None and score >= config.SCORE_THRESHOLD) and \
                               (distance is not None and distance <= config.DISTANCE_THRESHOLD):
                                success = True
                                break
                            # Partial: any metric meets EITHER threshold
                            elif (score is not None and score >= config.SCORE_THRESHOLD) or \
                                 (distance is not None and distance <= config.DISTANCE_THRESHOLD):
                                partial = True

                        if success:
                            mark_task_success(session, task)
                            terminal_status = True
                            logging.info(f"Task {task.id} marked as SUCCESS (at least one metric passed both thresholds).")
                        elif partial:
                            mark_task_partial(session, task)
                            terminal_status = True
                            logging.info(
                                f"Task {task.id} marked as PARTIAL (at least one metric passed one threshold).")
                            # DO NOT spawn fine-tune here; handled in periodic controller logic!
                        else:
                            # Retry logic: attempt again if attempts remain
                            if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
                                mark_task_retrying(session, task)
                                logging.info(f"Task {task.id} marked as RETRY: no metrics passed.")
                            else:
                                mark_task_failed(session, task, reason="Max attempts reached after worker_completed")
                                terminal_status = True
                                logging.info(f"Task {task.id} marked as FAILED: no metrics passed and max attempts reached.")

                        session.commit()
                        update_job_status(session, task.job_id)

                    elif task.status == STATUS_WORKER_FAILED:
                        # Worker failed: retry or mark as failed if out of attempts
                        if (task.attempt_count or 0) < (task.max_attempts or config.TASK_MAX_ATTEMPTS):
                            mark_task_retrying(session, task)
                            logging.info(f"Task {task.id} marked as RETRY after worker failure.")
                        else:
                            mark_task_failed(session, task, reason="Worker failure and max attempts reached")
                            terminal_status = True
                            logging.info(f"Task {task.id} marked as FAILED: worker failure and max attempts reached.")
                        session.commit()
                        update_job_status(session, task.job_id)

                    if terminal_status:
                        handle_terminal_task(r, task)

        except Exception as ex:
            logging.error(f"Error in post-worker status handling: {ex}")

        # --- PERIODIC PARTIAL TASK HANDLING (Fine-tune spawning by controller) ---
        try:
            with get_db() as session:
                handle_partial_tasks(session)
                session.commit()  # <--- Add this line!
        except Exception as ex:
            logging.error(f"Error in periodic partial task handling: {ex}")

        # --- CONTROLLER LOGIC (fine-tune, retry, queueing) ---
        # Queue eligible tasks to Redis for worker processing.
        # Only STATUS_NEW, STATUS_RETRYING, STATUS_FINE_TUNING are considered queueable.
        try:
            with get_db() as session:
                now = datetime.utcnow()
                eligible_status = [STATUS_NEW, STATUS_RETRYING, STATUS_FINE_TUNING]
                logging.debug(f"Querying tasks with eligible_status={eligible_status}")
                tasks = session.query(ControllerTask).filter(
                    ControllerTask.status.in_(eligible_status)
                ).all()
                logging.debug(f"Retrieved {len(tasks)} eligible tasks")
                if not tasks:
                    logging.info("No tasks eligible for queueing.")
                    time.sleep(POLL_INTERVAL)
                    continue

                # Score and sort tasks for queueing
                task_ids = [t.id for t in tasks]
                logging.debug(f"task_ids: {task_ids} (types: {[type(ti) for ti in task_ids]})")
                metrics_map = get_task_metric_scores(session, task_ids)
                logging.debug(f"metrics_map: {metrics_map}")

                scored_tasks = []
                for t in tasks:
                    logging.debug(f"Scoring task id={t.id} (type={type(t.id)})")
                    m = metrics_map.get(t.id, {})
                    t._distance = m.get('distance')
                    t._score = m.get('score')
                    t._priority = hybrid_priority(t)
                    logging.debug(f"Task {t.id} scored: distance={t._distance}, score={t._score}, priority={t._priority}")
                    scored_tasks.append(t)

                # Filter and sort queueable tasks
                queueable_status = [STATUS_NEW, STATUS_RETRYING, STATUS_FINE_TUNING]
                queueable = [
                    t for t in scored_tasks
                    if t.status in queueable_status
                    and (t.attempt_count or 0) < (t.max_attempts or config.TASK_MAX_ATTEMPTS)
                    and (t.fine_tune_depth or 0) <= config.MAX_FINE_TUNE_DEPTH
                    and not job_has_success(session, t.job_id)
                ]

                logging.debug(f"Found {len(queueable)} queueable tasks")
                new_tasks = [t for t in queueable if t.status == STATUS_NEW]
                other_tasks = [t for t in queueable if t.status != STATUS_NEW]

                new_tasks = sorted(new_tasks, key=lambda t: t._priority, reverse=True)
                other_tasks = sorted(other_tasks, key=lambda t: t._priority, reverse=True)

                batch = new_tasks[:MIN_NEW]
                fill_count = BATCH_SIZE - len(batch)
                batch += other_tasks[:fill_count]

                logging.debug(f"Batch to queue (length={len(batch)}): {[t.id for t in batch]}")
                for task in batch:
                    logging.debug(f"Preparing to queue task id={task.id}, type={type(task.id)}, job_id={task.job_id}, type(job_id)={type(task.job_id)}")
                    old_status = task.status
                    # Change task status to QUEUED and update timestamp
                    task.status = STATUS_QUEUED
                    task.updated_at = datetime.utcnow()
                    if old_status == STATUS_RETRYING:
                        task.attempt_count = (task.attempt_count or 0) + 1
                    session.commit()
                    update_job_status(session, task.job_id)
                    logging.debug(f"Committed task id={task.id}, now queuing to Redis")
                    queue_task_to_redis(r, task)
                    logging.debug(f"Queued task id={task.id} to Redis")

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