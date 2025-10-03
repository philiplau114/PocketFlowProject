import os
import time
import sys

# Import config from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def create_lock(lockfile):
    open(lockfile, 'w').close()

def remove_lock(lockfile):
    if os.path.exists(lockfile):
        os.remove(lockfile)

def wait_for_worker_paused(timeout=config.LOCK_WAIT_TIMEOUT_SECONDS):
    waited = 0
    print("Waiting for worker to acknowledge pause...")
    while not os.path.exists(config.WORKER_PAUSED_LOCK_FILE):
        time.sleep(2)
        waited += 2
        if waited > timeout:
            raise TimeoutError("Worker did not pause in time.")

def main():
    create_lock(config.TICKDATA_LOCK_FILE)
    wait_for_worker_paused()
    print("Worker paused. Safe to run batch jobs...")

    # Step 1: Update and export tick data
    os.system("python batch_update_and_export.py")

    # Step 2: Run correlation batch
    os.system("python batch_correlation_update.py")

    # Step 3: Run pip value batch
    os.system("python populate_pip_values.py")

    print("Batch jobs complete. Releasing locks.")
    remove_lock(config.TICKDATA_LOCK_FILE)
    remove_lock(config.WORKER_PAUSED_LOCK_FILE)

if __name__ == "__main__":
    main()