import os
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Load all configs from your central config.py
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ---- CCY Pairs (can move to .env as a comma-separated string if desired) ----
CCY_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURNZD", "EURCAD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPNZD", "GBPCAD",
    "AUDJPY", "AUDCHF", "AUDNZD", "AUDCAD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF",
    "CHFJPY"
]
if hasattr(config, "CCY_PAIRS") and config.CCY_PAIRS:
    # If you add CCY_PAIRS to your .env as a comma list
    CCY_PAIRS = [x.strip() for x in config.CCY_PAIRS.split(',') if x.strip()]

# ---- Load paths and credentials from config.py/.env ----
TICK_DATA_MANAGER_PATH = getattr(config, "TICK_DATA_MANAGER_PATH", r'"c:\Program Files (x86)\eareview.net\Tick Data Suite\Tick Data Manager.exe"')
EXPORT_FORMAT = getattr(config, "EXPORT_FORMAT", r'C:\Users\Philip\Documents\GitHub\PocketFlowProject\portfolio_analysis\export_H1_bars.bcf')
EXPORT_DIR = getattr(config, "EXPORT_DIR", r'C:\Users\Philip\Documents\GitHub\PocketFlowProject\portfolio_analysis\exported_bars')
TIMEFRAME = getattr(config, "CORRELATION_TIMEFRAME", 'H1')
DB_URL = getattr(config, "SQLALCHEMY_DATABASE_URL", None)
if not DB_URL:
    # Fallback: build from individual parts
    DB_URL = f"mysql+mysqlconnector://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"

def get_date_range():
    today = datetime.utcnow()
    start = today - timedelta(days=365)
    return start.strftime('%Y.%m.%d'), today.strftime('%Y.%m.%d')

def update_tick_data():
    cmd = (
        f'{TICK_DATA_MANAGER_PATH} /update:Dukascopy:{",".join(CCY_PAIRS)}'
    )
    print(f"Updating tick data:\n{cmd}")
    subprocess.run(cmd, shell=True, check=True)

def export_tick_data(start_date, end_date):
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)
    cmd = (
        f'{TICK_DATA_MANAGER_PATH} /export:Dukascopy:{",".join(CCY_PAIRS)}:{start_date}-{end_date} '
        f'/eformat:{EXPORT_FORMAT} /output:{EXPORT_DIR}'
    )
    print(f"Exporting tick data:\n{cmd}")
    subprocess.run(cmd, shell=True, check=True)

def load_h1_data(pair, start_date, end_date):
    file_name = f"Dukascopy-{pair}-{start_date}-{end_date}-bardata_H1.csv"
    file_path = os.path.join(EXPORT_DIR, file_name)
    df = pd.read_csv(file_path, sep=",")
    df.columns = df.columns.str.strip()
    df['datetime'] = pd.to_datetime(df['Date'] + " " + df['Time'])
    df.set_index('datetime', inplace=True)
    return df['Close']

def calc_log_returns(series):
    return np.log(series / series.shift(1)).dropna()

def calculate_correlation_matrix(close_dict):
    returns_dict = {pair: calc_log_returns(close_dict[pair]) for pair in close_dict}
    df = pd.DataFrame(returns_dict).dropna()
    corr_matrix = df.corr()
    return corr_matrix

def save_correlation_matrix_to_db(corr_matrix, timeframe, date_calculated, db_url):
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for symbol1 in corr_matrix.columns:
            for symbol2 in corr_matrix.index:
                corr = corr_matrix.loc[symbol1, symbol2]
                conn.execute(
                    text("""
                        INSERT INTO Correlation_Matrix (symbol1, symbol2, timeframe, correlation, date_calculated)
                        VALUES (:symbol1, :symbol2, :timeframe, :correlation, :date_calculated)
                        ON DUPLICATE KEY UPDATE correlation=:correlation, date_calculated=:date_calculated
                    """),
                    {
                        "symbol1": symbol1,
                        "symbol2": symbol2,
                        "timeframe": timeframe,
                        "correlation": float(corr),
                        "date_calculated": date_calculated,
                    },
                )

def main():
    start_date, end_date = get_date_range()
    update_tick_data()
    export_tick_data(start_date, end_date)
    close_dict = {}
    for pair in CCY_PAIRS:
        print(f"Loading H1 data for {pair}")
        close_dict[pair] = load_h1_data(pair, start_date, end_date)
    print("Calculating correlation matrix...")
    corr_matrix = calculate_correlation_matrix(close_dict)
    print(corr_matrix)
    date_calculated = datetime.utcnow()
    print("Saving correlation matrix to DB...")
    save_correlation_matrix_to_db(corr_matrix, TIMEFRAME, date_calculated, DB_URL)
    print("Done.")

if __name__ == "__main__":
    main()