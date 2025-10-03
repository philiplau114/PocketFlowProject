import os
import sys
from datetime import datetime, timedelta

# Ensure project root is in sys.path so config.py can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_date_range():
    today = datetime.utcnow()
    start = today - timedelta(days=config.CORRELATION_LOOKBACK_DAYS)
    return start.strftime('%Y.%m.%d'), today.strftime('%Y.%m.%d')

def update_tick_data():
    cmd = (
        f'{config.TICK_DATA_MANAGER_PATH} /update:Dukascopy:{",".join(config.CCY_PAIRS)}'
    )
    print(f"[batch_update_and_export] Updating tick data:\n{cmd}")
    os.system(cmd)

def export_tick_data(start_date, end_date):
    if not os.path.exists(config.EXPORT_DIR):
        os.makedirs(config.EXPORT_DIR)
    cmd = (
        f'{config.TICK_DATA_MANAGER_PATH} /export:Dukascopy:{",".join(config.CCY_PAIRS)}:{start_date}-{end_date} '
        f'/eformat:{config.EXPORT_FORMAT} /output:{config.EXPORT_DIR}'
    )
    print(f"[batch_update_and_export] Exporting tick data:\n{cmd}")
    os.system(cmd)

def main():
    start_date, end_date = get_date_range()
    update_tick_data()
    export_tick_data(start_date, end_date)
    print("[batch_update_and_export] Tick data update/export complete.")

if __name__ == "__main__":
    main()