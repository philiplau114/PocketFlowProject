import os
import glob
import pandas as pd
import argparse
from datetime import datetime
import sys

# Add the parent directory to sys.path so config.py at project root is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_pip_size(pair):
    """Return pip size. 0.01 for JPY pairs, else 0.0001."""
    return 0.01 if pair.endswith('JPY') else 0.0001

def extract_pair_from_filename(fname):
    # Dukascopy-AUDCHF-2022.09.30-2025.09.30-bardata_H1.csv
    parts = fname.split('-')
    return parts[1] if len(parts) > 1 else None

def get_latest_csv(pair, tickdata_dir):
    files = glob.glob(os.path.join(tickdata_dir, f"Dukascopy-{pair}-*-bardata_H1.csv"))
    files = sorted(files, key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0] if files else None

def get_last_close_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    return float(df.iloc[-1]['Close'])

def get_quote_ccy(pair):
    return pair[-3:]

def get_needed_quotes(pairs, account_ccy='USD'):
    needed = set()
    for pair in pairs:
        quote = get_quote_ccy(pair)
        if quote != account_ccy:
            needed.add(f"{account_ccy}{quote}")
    return needed

def pip_value_generic(pair, lot_size, pip_size, price, account_ccy, usd_quote_prices):
    quote_ccy = get_quote_ccy(pair)
    if quote_ccy == account_ccy:
        return lot_size * 100_000 * pip_size
    else:
        usd_quote = f"{account_ccy}{quote_ccy}"
        if usd_quote not in usd_quote_prices:
            raise ValueError(f"Missing conversion rate for {usd_quote}")
        return (lot_size * 100_000 * pip_size) / usd_quote_prices[usd_quote]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--account_ccy', type=str, default=config.ACCOUNT_CCY, help='Account currency, e.g. USD')
    parser.add_argument('--lot_size', type=float, default=0.01, help='Lot size for pip value calculation (default 0.01)')
    parser.add_argument('--tickdata_dir', type=str, default=config.TICKDATA_DIR, help='Path to tickdata directory')
    parser.add_argument('--lookback_days', type=int, default=getattr(config, 'CORRELATION_LOOKBACK_DAYS', 365), help='Lookback days for pip value date range')
    args = parser.parse_args()

    account_ccy = args.account_ccy.upper()
    lot_size = args.lot_size
    tickdata_dir = args.tickdata_dir
    lookback_days = args.lookback_days

    # Determine date range for file search
    from datetime import datetime, timedelta
    today = datetime.utcnow()
    start = today - timedelta(days=lookback_days)
    start_str = start.strftime('%Y.%m.%d')
    end_str = today.strftime('%Y.%m.%d')

    # Step 1: Use CCY_PAIRS from config to get all pairs
    all_pairs = config.CCY_PAIRS

    # Step 2: For all needed conversion rates, get latest price for account_ccy/quote
    needed_quotes = get_needed_quotes(all_pairs, account_ccy=account_ccy)
    usd_quote_prices = {}
    for quote in needed_quotes:
        latest_csv = get_latest_csv(quote, tickdata_dir)
        if latest_csv:
            usd_quote_prices[quote] = get_last_close_from_csv(latest_csv)

    # Step 3: For each FX pair, calculate pip value
    pip_value_records = []
    for pair in all_pairs:
        latest_csv = get_latest_csv(pair, tickdata_dir)
        if not latest_csv:
            print(f"Warning: No tickdata for {pair}. Skipping.")
            continue
        last_close = get_last_close_from_csv(latest_csv)
        pip_size = get_pip_size(pair)
        try:
            pipval = pip_value_generic(pair, lot_size, pip_size, last_close, account_ccy, usd_quote_prices)
            pip_value_records.append({
                'ccy_pair': pair,
                'account_ccy': account_ccy,
                'lot_size': lot_size,
                'pip_value': pipval,
                'value_date': datetime.utcnow().date(),
                'price_used': last_close,
                'quote_to_account_ccy_rate': usd_quote_prices.get(f"{account_ccy}{get_quote_ccy(pair)}", 1.0),
            })
        except Exception as e:
            print(f"Error for {pair}: {e}")

    # Step 4: Insert/update into controller DB using config DB settings
    import mysql.connector
    cnx = mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE
    )
    cursor = cnx.cursor()
    for rec in pip_value_records:
        sql = """
        INSERT INTO pip_values (ccy_pair, account_ccy, lot_size, pip_value, value_date, price_used, quote_to_account_ccy_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE pip_value=VALUES(pip_value), price_used=VALUES(price_used), quote_to_account_ccy_rate=VALUES(quote_to_account_ccy_rate)
        """
        cursor.execute(sql, (
            rec['ccy_pair'], rec['account_ccy'], rec['lot_size'], rec['pip_value'],
            rec['value_date'], rec['price_used'], rec['quote_to_account_ccy_rate']
        ))
    cnx.commit()
    cursor.close()
    cnx.close()
    print(f"Done populating pip values for lot size {lot_size}, account_ccy {account_ccy}!")

if __name__ == "__main__":
    main()