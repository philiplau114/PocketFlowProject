import os
import time
import logging
from dotenv import load_dotenv
from db_utils import get_db, get_stuck_tasks, requeue_task, get_inactive_workers

load_dotenv()

JOB_STUCK_THRESHOLD_MINUTES = int(os.getenv('JOB_STUCK_THRESHOLD_MINUTES', 60))
WORKER_INACTIVE_THRESHOLD_MINUTES = int(os.getenv('WORKER_INACTIVE_THRESHOLD_MINUTES', 5))
SUPERVISOR_POLL_INTERVAL = int(os.getenv('SUPERVISOR_POLL_INTERVAL', 60))

logging.basicConfig(level=logging.INFO)

def main():
    while True:
        try:
            with get_db() as session:
                stuck_tasks = get_stuck_tasks(session, threshold_minutes=JOB_STUCK_THRESHOLD_MINUTES)
                for task in stuck_tasks:
                    logging.warning(f"Task {task.id} stuck for over {JOB_STUCK_THRESHOLD_MINUTES} min. Re-queueing.")
                    requeue_task(session, task)
                    # (You can add notification/alert here)

                inactive_workers = get_inactive_workers(session, threshold_minutes=WORKER_INACTIVE_THRESHOLD_MINUTES)
                for worker_id in inactive_workers:
                    logging.warning(f"Worker {worker_id} inactive for over {WORKER_INACTIVE_THRESHOLD_MINUTES} min.")
                    # (You can add notification/alert here)
        except Exception as e:
            logging.error("Supervisor error: %s", e)
        time.sleep(SUPERVISOR_POLL_INTERVAL)

if __name__ == "__main__":
    main()