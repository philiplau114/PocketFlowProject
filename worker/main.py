import os
import time
import json
import logging
import redis
import subprocess
from datetime import datetime

from db_utils import (
    update_task_status, create_attempt, finish_attempt, get_db,
    update_task_worker_job, update_task_heartbeat  # <--- Import heartbeat util
)
from db_sync import sync_test_metrics, sync_trade_records, sync_artifacts, sync_ai_suggestions

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_QUEUE = os.getenv('REDIS_QUEUE', 'pfai_tasks')
WORKER_ID = os.getenv('WORKER_ID', f'worker_{os.getpid()}')
UIROBOT_PATH = os.getenv('UIPATH_CLI', r"C:\Users\Philip\AppData\Local\Programs\UiPath\Studio\UiRobot.exe")
PACKAGE_PATH = os.getenv('UIPATH_WORKFLOW', r"C:\Users\Philip\Documents\UiPath\Packages\MT4.Backtesting.Automation.1.0.1-alpha.2.nupkg")

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
    """
    Parse UiPath output for expected output arguments.
    UiPath will typically print output arguments as JSON to stdout.
    """
    try:
        # Try to find the first valid JSON object in stdout
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                output = json.loads(line)
                return output
    except Exception as e:
        logging.warning(f"Failed to parse UiPath output as JSON: {e}")
    return {}

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
                # Initial heartbeat update
                update_task_heartbeat(session, task_id)
                attempt_id = create_attempt(session, task_id, status="in_progress")

            try:
                # Heartbeat/progress update loop
                start_time = time.time()
                last_heartbeat = start_time
                result = None
                uipath_outputs = {}
                # Launch the process and poll:
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
                while True:
                    # Heartbeat update every HEARTBEAT_INTERVAL seconds
                    now = time.time()
                    if now - last_heartbeat > HEARTBEAT_INTERVAL:
                        with get_db() as session:
                            update_task_heartbeat(session, task_id)
                        last_heartbeat = now
                    # Poll if process finished
                    if process.poll() is not None:
                        break
                    time.sleep(5)
                # Process finished, collect results
                stdout, stderr = process.communicate()
                returncode = process.returncode
                if returncode == 0:
                    uipath_outputs = parse_uipath_output(stdout)
                else:
                    uipath_outputs = {}
                out_worker_JobId = uipath_outputs.get("out_worker_JobId")
                out_Status = uipath_outputs.get("out_Status", "Failed" if returncode != 0 else "Completed")
                out_Artifacts = uipath_outputs.get("out_Artifacts")
                out_ErrorMessage = uipath_outputs.get("out_ErrorMessage", stderr if returncode != 0 else None)

                status = "completed" if out_Status.lower() == "completed" else "failed"
                error_message = out_ErrorMessage
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
                out_worker_JobId = None  # Ensure it's set for next block

            with get_db() as session:
                update_task_status(session, task_id, status)
                update_task_heartbeat(session, task_id)  # Final heartbeat on finish
                finish_attempt(session, attempt_id, status, error_message, result_json)
                if out_worker_JobId:
                    try:
                        update_task_worker_job(session, task_id, int(out_worker_JobId))
                        logging.info(f"Updated worker_job_id={out_worker_JobId} for controller task {task_id}")
                    except Exception as e:
                        logging.warning(f"Failed to update worker_job_id for task {task_id}: {e}")

            # === Add this block ===
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