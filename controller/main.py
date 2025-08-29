import time
import logging
import redis
import json
from pathlib import Path
from db_utils import extract_setfile_metadata, insert_job_and_task, get_db
from config import WATCH_FOLDER, REDIS_HOST, REDIS_PORT, REDIS_QUEUE, USER_ID

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
                    # Optionally add more extracted fields here if needed
                }
                r.lpush(REDIS_QUEUE, json.dumps(task_data))
                processed_files.add(file.name)
                logging.info("Queued new task: %s", file.name)
            except Exception as e:
                logging.error("Failed to process file %s: %s", file.name, e)
        time.sleep(10)

if __name__ == "__main__":
    main()