import os
import time
import json
import logging
import redis
import subprocess
import threading
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

def run_uipath(set_file, job_id, task_id):
    # Prepare input arguments matching UiPath workflow requirements
    input_args = {
        "in_JobId": str(job_id),
        "in_TaskId": str(task_id),
        "in_InputSetFilePath": set_file
    }
    input_args_json = json.dumps(input_args)

    cmd = [
        UIROBOT_PATH,
        "execute",
        "--file", PACKAGE_PATH,
        "--input", input_args_json
    ]
    logging.info(f"Running UiPath: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def parse_uipath_output(stdout):
    try:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                output = json.loads(line)
                return output
    except Exception as e:
        logging.warning(f"Failed to parse UiPath output as JSON: {e}")
    return {}

def notify_kill(task_id, reason, extra=None):
    subject = f"[Worker Kill] Task {task_id} killed due to {reason}"
    body = f"Task {task_id} killed.\nReason: {reason}\n"
    if extra:
        body += f"Details: {extra}\n"
    send_email(subject, body)
    send_telegram(body)
    logging.warning(body)

def monitor_kill_signal(process, task_id, killed_flag, kill_file=KILL_SIGNAL_FILE):
    """
    Monitor for a kill file; if present, kill the process and set killed_flag[0]=True.
    """
    while process.poll() is None:
        if os.path.exists(kill_file):
            try:
                process.kill()
                killed_flag[0] = True
                notify_kill(task_id, "manual kill via kill file", f"Kill file: {kill_file}")
                logging.warning(f"Process killed for task {task_id} due to manual kill signal.")
                os.remove(kill_file)  # Clean up the kill file after killing
                break
            except Exception as e:
                logging.error(f"Failed to kill process for task {task_id}: {e}")
        time.sleep(5)

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
                result = None
                uipath_outputs = {}

                # Start UiPath process
                process = subprocess.Popen(
                    [
                        UIROBOT_PATH,
                        "execute",
                        "--file", PACKAGE_PATH,
                        "--input", json.dumps({
                            "in_JobId": str(job_id),
                            "in_TaskId": str(task_id),
                            "in_InputSetFilePath": set_file
                        })
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                killed_flag = [False]
                kill_thread = threading.Thread(target=monitor_kill_signal, args=(process, task_id, killed_flag))
                kill_thread.daemon = True
                kill_thread.start()

                while True:
                    now = time.time()
                    if now - last_heartbeat > HEARTBEAT_INTERVAL:
                        with get_db() as session:
                            update_task_heartbeat(session, task_id)
                        last_heartbeat = now

                    elapsed = now - start_time
                    if elapsed > MAX_EXEC_SECONDS and process.poll() is None:
                        # Timeout exceeded; kill process and notify
                        try:
                            process.kill()
                            killed_flag[0] = True
                            notify_kill(task_id, f"timeout > {MAX_EXEC_SECONDS} sec", f"Elapsed: {elapsed:.1f} sec")
                            logging.warning(f"Process killed for task {task_id} due to timeout ({elapsed:.1f} sec).")
                        except Exception as e:
                            logging.error(f"Failed to kill process for task {task_id} on timeout: {e}")
                        break

                    if process.poll() is not None:
                        break

                    time.sleep(5)

                stdout, stderr = process.communicate()
                returncode = process.returncode
                if killed_flag[0]:
                    out_Status = "Killed"
                    status = "failed"
                    error_message = "Process killed (timeout/manual)"
                    uipath_outputs = {}
                elif returncode == 0:
                    uipath_outputs = parse_uipath_output(stdout)
                    out_Status = uipath_outputs.get("out_Status", "Completed")
                    status = "completed" if out_Status.lower() == "completed" else "failed"
                    error_message = uipath_outputs.get("out_ErrorMessage")
                else:
                    uipath_outputs = {}
                    out_Status = "Failed"
                    status = "failed"
                    error_message = stderr

                out_worker_JobId = uipath_outputs.get("out_worker_JobId")
                out_Artifacts = uipath_outputs.get("out_Artifacts")
                out_ErrorMessage = uipath_outputs.get("out_ErrorMessage", stderr if returncode != 0 else None)
                result_json = json.dumps({
                    "stdout": stdout,
                    "stderr": stderr,
                    "out_worker_JobId": out_worker_JobId,
                    "out_Status": out_Status,
                    "out_Artifacts": out_Artifacts,
                    "out_ErrorMessage": out_ErrorMessage
                })

            except Exception as e:
                status = "failed"
                error_message = str(e)
                result_json = None
                out_worker_JobId = None

            with get_db() as session:
                update_task_status(session, task_id, status)
                update_task_heartbeat(session, task_id)
                finish_attempt(session, attempt_id, status, error_message, result_json)
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