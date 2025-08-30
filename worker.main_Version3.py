import os
import time
import json
import logging
import redis
import subprocess
import threading
import tempfile

from datetime import datetime

from db_utils import (
    update_task_status, create_attempt, finish_attempt, get_db,
    update_task_worker_job, update_task_heartbeat
)
from .db_sync import sync_test_metrics, sync_trade_records, sync_artifacts, sync_ai_suggestions
from notify import send_email, send_telegram

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_QUEUE = os.getenv('REDIS_QUEUE', 'pfai_tasks')
WORKER_ID = os.getenv('WORKER_ID', f'worker_{os.getpid()}')
UIROBOT_PATH = os.getenv('UIPATH_CLI', r"C:\Users\Philip\AppData\Local\Programs\UiPath\Studio\UiRobot.exe")
PACKAGE_PATH = os.getenv('UIPATH_WORKFLOW', r"C:\Users\Philip\Documents\UiPath\Packages\MT4.Backtesting.Automation.1.0.1-alpha.2.nupkg")
MAX_EXEC_SECONDS = int(os.getenv('UIPATH_JOB_MAX_SECONDS', 12 * 3600))  # default 12 hours
KILL_SIGNAL_FILE = os.getenv('UIPATH_KILL_FILE', 'kill_worker.txt')     # kill file path

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
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    HEARTBEAT_INTERVAL = 300  # seconds (5 min)
    while True:
        try:
            task_json = r.rpop(REDIS_QUEUE)
            if not task_json:
                time.sleep(5)
                continue
            task = json.loads(task_json)
            set_file = task['set_file']
            job_id = task['job_id']
            task_id = task['task_id']

            logging.info(f"Picked up task {task_id} for set file {set_file}")

            with get_db() as session:
                update_task_status(session, task_id, "in_progress", assigned_worker=WORKER_ID)
                update_task_heartbeat(session, task_id)
                attempt_id = create_attempt(session, task_id, status="in_progress")

            try:
                start_time = time.time()
                last_heartbeat = start_time

                # Generate a unique output JSON path
                tmp_dir = tempfile.gettempdir()
                output_json_path = os.path.join(
                    tmp_dir,
                    f"uipath_output_{job_id}_{task_id}_{int(time.time())}.json"
                )

                # Start UiPath process with output path
                process = subprocess.Popen(
                    [
                        UIROBOT_PATH,
                        "execute",
                        "--file", PACKAGE_PATH,
                        "--input", json.dumps({
                            "in_JobId": str(job_id),
                            "in_TaskId": str(task_id),
                            "in_InputSetFilePath": set_file,
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
                        if os.path.exists(KILL_SIGNAL_FILE):
                            try:
                                process.kill()
                                killed_flag[0] = True
                                notify_kill(task_id, "manual kill via kill file", f"Kill file: {KILL_SIGNAL_FILE}")
                                logging.warning(f"Process killed for task {task_id} due to manual kill signal.")
                                os.remove(KILL_SIGNAL_FILE)
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
                    if elapsed > MAX_EXEC_SECONDS:
                        logging.error(f"MAX_EXEC_SECONDS reached ({elapsed}s): Killing UiPath process for task {task_id}")
                        process.kill()
                        killed_flag[0] = True
                        out_Status = "Timeout"
                        error_message = f"Timeout: UiPath process exceeded {MAX_EXEC_SECONDS} seconds"
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
                            if file_parse_attempts % 5 == 0:
                                logging.warning(f"Unreadable output JSON for task {task_id} (attempt {file_parse_attempts}): {e}")
                            time.sleep(2)
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

            except Exception as e:
                out_Status = "Failed"
                error_message = str(e)
                result_json_blob = None
                out_worker_JobId = None

            # Finalize DB
            status = "completed" if (out_Status and out_Status.lower() == "completed") else "failed"
            with get_db() as session:
                update_task_status(session, task_id, status)
                update_task_heartbeat