import time
import logging
import redis
import json
import signal
import sys
from pathlib import Path
from db_utils import extract_setfile_metadata, insert_job_and_task, get_db
from dotenv import load_dotenv
import os

# Load .env.controller first (if present), then .env for defaults
load_dotenv('.env.controller', override=True)
load_dotenv('.env', override=False)

from config import WATCH_FOLDER, REDIS_HOST, REDIS_PORT, REDIS_QUEUE, USER_ID
from notify import send_email, send_telegram

logging.basicConfig(level=logging.INFO)

stop_flag = False

def handle_stop_signal(sig, frame):
    global stop_flag
    logging.info("Received stop signal, will exit after this iteration.")
    stop_flag = True

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, handle_stop_signal)
signal.signal(signal.SIGTERM, handle_stop_signal)

def main():
    processed_files = set()
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    while not stop_flag:
        for file in Path(WATCH_FOLDER).glob("*.set"):
            if file.name in processed_files:
                continue
            try:
                meta = extract_setfile_metadata(str(file))
                with get_db() as session:
                    job_id, task_id, is_new = insert_job_and_task(session, meta, str(file), user_id=USER_ID)
                if not is_new:
                    logging.info("Already processed or queued: %s", file.name)
                    processed_files.add(file.name)
                    continue  # Don't push duplicate to Redis!
                task_data = {
                    "job_id": job_id,
                    "task_id": task_id,
                    "set_file": str(file),
                    "ea_name": meta.get("ea_name"),
                    "symbol": meta.get("symbol"),
                    "timeframe": meta.get("timeframe"),
                }
                r.lpush(REDIS_QUEUE, json.dumps(task_data))
                processed_files.add(file.name)
                logging.info("Queued new task: %s", file.name)
            except Exception as e:
                error_msg = f"Failed to process file {file.name}: {e}"
                logging.error(error_msg)
                subject = f"Task File Processing Failed: {file.name}"
                body = f"{error_msg}\n\nPlease check the file and system logs."
                send_email(subject, body)
                send_telegram(body)
        time.sleep(10)
    logging.info("Controller stopped gracefully.")

if __name__ == "__main__":
    main()