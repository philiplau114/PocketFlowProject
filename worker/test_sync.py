# test_sync.py

from db_sync import (
    sync_test_metrics,
    sync_artifacts,
    sync_ai_suggestions,
)
import pymysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

def main():
    out_worker_JobId = 1
    print(f"[DEBUG] Syncing data for out_worker_JobId = {out_worker_JobId}")

    # Open ONE MySQL connection for the whole sync
    ctrl_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT,
        charset='utf8mb4',
        autocommit=False
    )

    try:
        print("[DEBUG] Calling sync_test_metrics...")
        sync_test_metrics(out_worker_JobId, ctrl_conn)

        print("[DEBUG] Calling sync_artifacts...")
        sync_artifacts(out_worker_JobId, ctrl_conn)

        print("[DEBUG] Calling sync_ai_suggestions...")
        sync_ai_suggestions(out_worker_JobId, ctrl_conn)

        ctrl_conn.commit()
        print("[DEBUG] All sync functions called and committed.")
    except Exception as e:
        ctrl_conn.rollback()
        print(f"[ERROR] Main sync failed and rolled back: {e}")
    finally:
        ctrl_conn.close()

if __name__ == "__main__":
    main()