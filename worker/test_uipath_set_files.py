import os
import subprocess
import json
import time
import logging

# Paths (adjust if needed)
SET_FILES_DIR = r"C:\Users\Philip\Documents\GitHub\EA_Automation\01_user_inputs"
UIPATH_WORKFLOW = r"C:\Users\Philip\Documents\UiPath\Packages\MT4.Backtesting.Automation.1.0.6.nupkg"
UIPATH_CLI = r"C:\Users\Philip\AppData\Local\Programs\UiPath\Studio\UiRobot.exe"
UIPATH_CONFIG = r"C:\Users\Philip\Documents\UiPath\Packages\Config.xlsx"
OUTPUT_JSON_DIR = r"C:\Users\Philip\Documents\GitHub\EA_Automation\02_backtest"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnitTest")

def run_uipath_for_set(set_file_path, job_id, task_id):
    output_json_path = os.path.join(
        OUTPUT_JSON_DIR,
        f"uipath_output_{job_id}_{task_id}_{int(time.time())}.json"
    )
    uipath_input = {
        "in_JobId": str(job_id),
        "in_TaskId": str(task_id),
        "in_InputSetFilePath": set_file_path,
        "in_OutputJsonPath": output_json_path,
        "in_ConfigPath": UIPATH_CONFIG
    }
    logger.info(f"Running UiPath for {set_file_path} (job_id={job_id}, task_id={task_id})")
    process = subprocess.Popen(
        [
            UIPATH_CLI,
            "execute",
            "--file", UIPATH_WORKFLOW,
            "--input", json.dumps(uipath_input)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Wait for process to finish
    stdout, stderr = process.communicate()
    logger.info(f"UiPath stdout: {stdout}")
    logger.info(f"UiPath stderr: {stderr}")

    # Wait for output JSON
    max_wait = 120  # seconds
    waited = 0
    while waited < max_wait:
        if os.path.exists(output_json_path):
            logger.info(f"Output JSON ready: {output_json_path}")
            with open(output_json_path, "r", encoding="utf-8") as f:
                try:
                    result = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading JSON: {e}")
                    result = None
            break
        time.sleep(2)
        waited += 2
    else:
        logger.error(f"Timeout waiting for output JSON: {output_json_path}")
        result = None

    # Cleanup output file (optional)
    try:
        if os.path.exists(output_json_path):
            os.remove(output_json_path)
    except Exception as cleanup_err:
        logger.warning(f"Failed to remove output file: {output_json_path}: {cleanup_err}")

    return result

def main():
    set_files = [f for f in os.listdir(SET_FILES_DIR) if f.lower().endswith('.set')]
    logger.info(f"Found {len(set_files)} .set files to test.")
    job_id = 2
    task_id = 2

    for set_file in set_files:
        set_file_path = os.path.join(SET_FILES_DIR, set_file)
        result = run_uipath_for_set(set_file_path, job_id, task_id)
        print(f"=== Results for {set_file} ===")
        print(json.dumps(result, indent=2))
        job_id += 1
        task_id += 1

if __name__ == "__main__":
    main()