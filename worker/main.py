from dotenv import load_dotenv
import os
import time
import json
import logging
import redis
import subprocess
import threading
import tempfile
from datetime import datetime

# Load .env.worker first for overrides, then .env for defaults
load_dotenv('.env.worker', override=True)
load_dotenv('.env', override=False)

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_QUEUE, WORKER_ID,
    UIPATH_CLI, UIPATH_WORKFLOW, UIPATH_JOB_MAX_SECONDS, UIPATH_KILL_FILE, SET_FILE_LIBRARY,
    OUTPUT_JSON_DIR, OUTPUT_JSON_POLL_INTERVAL, OUTPUT_JSON_WARNING_MODULUS
)
from db_utils import (
    update_task_status, create_attempt, finish_attempt, get_db,
    update_task_worker_job, update_task_heartbeat
)
from .db_sync import sync_test_metrics, sync_trade_records, sync_artifacts, sync_ai_suggestions
from notify import send_email, send_telegram

logging.basicConfig(level=logging.INFO)

def notify_kill(task_id, reason, extra=None):
    subject = f"[Worker Kill] Task {task_id} killed due to {reason}"
    body = f"Task {task_id} killed.\nReason: {reason}\n"
    if extra:
        body += f"Details: {extra}\n"
    send_email(subject, body)
    send_telegram(body)
    logging.warning(body)

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)  # decode_responses=False for binary data

    HEARTBEAT_INTERVAL = 300  # seconds (5 min)
    while True:
        try:
            task_json = r.rpop(REDIS_QUEUE)
            if not task_json:
                time.sleep(5)
                continue
            # Parse JSON using utf-8 since decode_responses=False
            if isinstance(task_json, bytes):
                task_json = task_json.decode("utf-8")
            task = json.loads(task_json)
            job_id = task['job_id']
            task_id = task['task_id']
            set_file_name = task['set_file_name']
            input_blob_key = task['input_blob_key']

            # --- NEW BLOCK: Fetch file_blob from Redis, write to temp file ---
            file_blob = r.get(input_blob_key)
            if not file_blob:
                raise Exception(f"Cannot find file_blob in Redis for key {input_blob_key}")
            set_file_path = os.path.join(SET_FILE_LIBRARY, set_file_name)
            with open(set_file_path, "wb") as f:
                f.write(file_blob)
            logging.info(f"Wrote input set file for task {task_id}: {set_file_path}")
            # --- END NEW BLOCK ---

            logging.info(f"Picked up task {task_id} for set file {set_file_path}")

            with get_db() as session:
                update_task_status(session, task_id, "in_progress", assigned_worker=WORKER_ID)
                update_task_heartbeat(session, task_id)
                attempt_id = create_attempt(session, task_id, status="in_progress")

            try:
                start_time = time.time()
                last_heartbeat = start_time

                # Generate a unique output JSON path
                output_json_path = os.path.join(
                    OUTPUT_JSON_DIR,
                    f"uipath_output_{job_id}_{task_id}_{int(time.time())}.json"
                )

                # Start UiPath process with output path
                process = subprocess.Popen(
                    [
                        UIPATH_CLI,
                        "execute",
                        "--file", UIPATH_WORKFLOW,
                        "--input", json.dumps({
                            "in_JobId": str(job_id),
                            "in_TaskId": str(task_id),
                            "in_InputSetFilePath": set_file_path,
                            "in_OutputJsonPath": output_json_path
                        })
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                killed_flag = [False]
                error_message = None
                out_Status = None
                out_worker_JobId = None
                out_Artifacts = None
                uipath_outputs = None

                def monitor_kill_signal():
                    while process.poll() is None:
                        if os.path.exists(UIPATH_KILL_FILE):
                            try:
                                process.kill()
                                killed_flag[0] = True
                                notify_kill(task_id, "manual kill via kill file", f"Kill file: {UIPATH_KILL_FILE}")
                                logging.warning(f"Process killed for task {task_id} due to manual kill signal.")
                                os.remove(UIPATH_KILL_FILE)
                                break
                            except Exception as e:
                                logging.error(f"Failed to kill process for task {task_id}: {e}")
                        time.sleep(2)

                kill_thread = threading.Thread(target=monitor_kill_signal)
                kill_thread.daemon = True
                kill_thread.start()

                # Main supervision loop
                json_ready = False
                file_parse_attempts = 0
                last_grace_after_json = None
                result_json_blob = None

                while True:
                    now = time.time()
                    elapsed = now - start_time
                    # Heartbeat
                    if now - last_heartbeat > HEARTBEAT_INTERVAL:
                        with get_db() as session:
                            update_task_heartbeat(session, task_id)
                        last_heartbeat = now

                    # Timeout
                    if elapsed > UIPATH_JOB_MAX_SECONDS:
                        logging.error(f"UIPATH_JOB_MAX_SECONDS reached ({elapsed}s): Killing UiPath process for task {task_id}")
                        process.kill()
                        killed_flag[0] = True
                        out_Status = "Timeout"
                        error_message = f"Timeout: UiPath process exceeded {UIPATH_JOB_MAX_SECONDS} seconds"
                        break

                    # Output JSON supervision
                    if os.path.exists(output_json_path):
                        try:
                            with open(output_json_path, "r", encoding="utf-8") as f:
                                uipath_outputs = json.load(f)
                            json_ready = True
                            logging.info(f"Output JSON ready for task {task_id}: {uipath_outputs}")
                        except Exception as e:
                            file_parse_attempts += 1
                            if file_parse_attempts % OUTPUT_JSON_WARNING_MODULUS == 0:
                                logging.warning(f"Unreadable output JSON for task {task_id} (attempt {file_parse_attempts}): {e}")
                            time.sleep(OUTPUT_JSON_POLL_INTERVAL)
                            continue

                    if json_ready:
                        # Once JSON is ready, kill UiPath process if still running and exit loop
                        if process.poll() is None:
                            logging.info(f"Killing UiPath process for task {task_id} after output JSON is ready.")
                            process.kill()
                        out_Status = uipath_outputs.get("out_Status", "Unknown")
                        error_message = uipath_outputs.get("out_ErrorMessage")
                        out_worker_JobId = uipath_outputs.get("out_worker_JobId")
                        out_Artifacts = uipath_outputs.get("out_Artifacts")
                        result_json_blob = json.dumps(uipath_outputs)
                        break

                    # If process exited but no JSON yet, allow short grace period for file flush
                    if process.poll() is not None and not json_ready:
                        if last_grace_after_json is None:
                            last_grace_after_json = now
                        elif now - last_grace_after_json > 10:
                            # 10 seconds grace for file to be flushed after process exit
                            out_Status = "Failed"
                            error_message = "UiPath process exited but output JSON not produced"
                            break
                        time.sleep(1)
                        continue

                    # Handle killed process
                    if killed_flag[0]:
                        out_Status = "Killed"
                        error_message = "Process killed (timeout/manual)"
                        break

                    time.sleep(2)

                # Collect stdout/stderr for logging
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except Exception as e:
                    stdout = ""
                    stderr = f"Failed to collect stdout/stderr: {e}"

                if not result_json_blob:
                    result_json_blob = json.dumps({
                        "stdout": stdout,
                        "stderr": stderr,
                        "out_worker_JobId": out_worker_JobId,
                        "out_Status": out_Status,
                        "out_Artifacts": out_Artifacts,
                        "out_ErrorMessage": error_message
                    })

                # Cleanup output JSON
                try:
                    if os.path.exists(output_json_path):
                        os.remove(output_json_path)
                except Exception as cleanup_err:
                    logging.warning(f"Failed to remove temp output file: {output_json_path}: {cleanup_err}")

                # Cleanup input set file
                try:
                    if os.path.exists(set_file_path):
                        os.remove(set_file_path)
                except Exception as cleanup_err:
                    logging.warning(f"Failed to remove temp set file: {set_file_path}: {cleanup_err}")

            except Exception as e:
                out_Status = "Failed"
                error_message = str(e)
                result_json_blob = None
                out_worker_JobId = None

            # Finalize DB
            status = "completed" if (out_Status and out_Status.lower() == "completed") else "failed"
            with get_db() as session:
                update_task_status(session, task_id, status)
                update_task_heartbeat(session, task_id)
                finish_attempt(session, attempt_id, status, error_message, result_json_blob)
                if out_worker_JobId:
                    try:
                        update_task_worker_job(session, task_id, int(out_worker_JobId))
                        logging.info(f"Updated worker_job_id={out_worker_JobId} for controller task {task_id}")
                    except Exception as e:
                        logging.warning(f"Failed to update worker_job_id for task {task_id}: {e}")

            if status == "completed" and out_worker_JobId:
                try:
                    sync_test_metrics(out_worker_JobId)
                    sync_trade_records(out_worker_JobId)
                    sync_artifacts(out_worker_JobId)
                    sync_ai_suggestions(out_worker_JobId)
                    logging.info(f"Synchronized all databases for worker_job_id={out_worker_JobId}")
                except Exception as e:
                    logging.error(f"Error during DB sync for worker_job_id={out_worker_JobId}: {e}")

        except Exception as e:
            logging.error("Worker loop error: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    main()