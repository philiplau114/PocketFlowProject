import time
import logging
import redis
import json
from pathlib import Path
from db_utils import extract_setfile_metadata, insert_job_and_task, get_db
from config import WATCH_FOLDER, REDIS_HOST, REDIS_PORT, REDIS_QUEUE, USER_ID
from notify import send_email, send_telegram

logging.basicConfig(level=logging.INFO)

def main():
    processed_files = set()
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    while True:
        for file in Path(WATCH_FOLDER).glob("*.set"):
            if file.name in processed_files:
                continue
            try:
                meta = extract_setfile_metadata(str(file))
                with get_db() as session:
                    job_id, task_id = insert_job_and_task(session, meta, str(file), user_id=USER_ID)
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
                # Notification for task file processing failure
                subject = f"Task File Processing Failed: {file.name}"
                body = f"{error_msg}\n\nPlease check the file and system logs."
                send_email(subject, body)
                send_telegram(body)
        time.sleep(10)

if __name__ == "__main__":
    main()