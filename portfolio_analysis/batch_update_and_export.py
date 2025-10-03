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

def quote_path(path):
    # Add quotes if not already present (prevents double quoting)
    if not (path.startswith('"') and path.endswith('"')):
        return f'"{path}"'
    return path

def update_tick_data():
    tick_data_manager = quote_path(config.TICK_DATA_MANAGER_PATH)
    pairs = ",".join(config.CCY_PAIRS)
    cmd = f'{tick_data_manager} /update:Dukascopy:{pairs}'
    print(f"[batch_update_and_export] Updating tick data:\n{cmd}")
    os.system(cmd)

def export_tick_data(start_date, end_date):
    if not os.path.exists(config.EXPORT_DIR):
        os.makedirs(config.EXPORT_DIR)
    tick_data_manager = quote_path(config.TICK_DATA_MANAGER_PATH)
    pairs = ",".join(config.CCY_PAIRS)
    cmd = (
        f'{tick_data_manager} /export:Dukascopy:{pairs}:{start_date}-{end_date} '
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