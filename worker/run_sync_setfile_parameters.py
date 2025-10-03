import pymysql
from db_sync import sync_setfile_parameters
import config

def main():
    # Connect to the MySQL controller DB using values from config.py
    conn = pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset="utf8mb4"
    )

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT controller_task_id FROM test_metrics")
        results = cursor.fetchall()
        controller_task_ids = [row[0] for row in results if row[0] is not None]
        print(f"Found {len(controller_task_ids)} unique controller_task_id(s).")

        for controller_task_id in controller_task_ids:
            print(f"Processing controller_task_id: {controller_task_id}")
            sync_setfile_parameters(conn, controller_task_id)

        conn.commit()  # Commit all changes at the end (per your conventions)
        print("All setfile parameter syncs completed and committed.")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()