# test_sync.py

# Adjust the import as needed based on your project structure.
# If running from the same directory as db_sync.py:
from db_sync import (
    sync_test_metrics,
    sync_trade_records,
    sync_artifacts,
    sync_ai_suggestions,
)

def main():
    out_worker_JobId = 1
    print(f"Syncing data for out_worker_JobId = {out_worker_JobId}")

    print("Calling sync_test_metrics...")
    sync_test_metrics(out_worker_JobId)

    print("Calling sync_trade_records...")
    sync_trade_records(out_worker_JobId)

    print("Calling sync_artifacts...")
    sync_artifacts(out_worker_JobId)

    print("Calling sync_ai_suggestions...")
    sync_ai_suggestions(out_worker_JobId)

    print("All sync functions called.")

if __name__ == "__main__":
    main()