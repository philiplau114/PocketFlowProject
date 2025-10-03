import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Ensure project root is in sys.path so config.py can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_date_range():
    today = datetime.utcnow()
    start = today - timedelta(days=config.CORRELATION_LOOKBACK_DAYS)
    return start.strftime('%Y.%m.%d'), today.strftime('%Y.%m.%d')

def load_h1_data(pair, start_date, end_date):
    file_name = f"Dukascopy-{pair}-{start_date}-{end_date}-bardata_H1.csv"
    file_path = os.path.join(config.EXPORT_DIR, file_name)
    if not os.path.exists(file_path):
        print(f"[batch_correlation_update] WARNING: Missing exported data for {pair}: {file_path}")
        return None
    df = pd.read_csv(file_path, sep=",")
    df.columns = df.columns.str.strip()
    df['datetime'] = pd.to_datetime(df['Date'] + " " + df['Time'])
    df.set_index('datetime', inplace=True)
    return df['Close']

def calc_log_returns(series):
    return np.log(series / series.shift(1)).dropna()

def calculate_correlation_matrix(close_dict):
    returns_dict = {pair: calc_log_returns(close_dict[pair]) for pair in close_dict if close_dict[pair] is not None}
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
    close_dict = {}
    for pair in config.CCY_PAIRS:
        print(f"[batch_correlation_update] Loading H1 data for {pair}")
        close_dict[pair] = load_h1_data(pair, start_date, end_date)
    print("[batch_correlation_update] Calculating correlation matrix...")
    corr_matrix = calculate_correlation_matrix(close_dict)
    print(corr_matrix)
    date_calculated = datetime.utcnow()
    print("[batch_correlation_update] Saving correlation matrix to DB...")
    save_correlation_matrix_to_db(
        corr_matrix,
        getattr(config, "CORRELATION_TIMEFRAME", "H1"),
        date_calculated,
        getattr(config, "SQLALCHEMY_DATABASE_URL", None)
    )
    print("[batch_correlation_update] Done.")

if __name__ == "__main__":
    main()