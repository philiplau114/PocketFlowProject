import os
import sys
import pandas as pd
import argparse
from datetime import datetime, timedelta

# Add the parent directory to sys.path so config.py at project root is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_pip_size(pair):
    """Return pip size. 0.01 for JPY pairs, else 0.0001."""
    return 0.01 if pair.endswith('JPY') else 0.0001

def get_quote_ccy(pair):
    return pair[-3:]

def get_exported_csv(pair, start_date, end_date, export_dir):
    file_name = f"Dukascopy-{pair}-{start_date}-{end_date}-bardata_H1.csv"
    file_path = os.path.join(export_dir, file_name)
    if not os.path.exists(file_path):
        return None
    return file_path

def get_last_close_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    return float(df.iloc[-1]['Close'])

def get_needed_quotes(pairs, account_ccy='USD'):
    needed = set()
    for pair in pairs:
        quote = get_quote_ccy(pair)
        if quote != account_ccy:
            needed.add(f"{account_ccy}{quote}")
    return needed

def get_or_synth_close(pair, start_date, end_date, export_dir):
    # Try direct
    file_path = get_exported_csv(pair, start_date, end_date, export_dir)
    if file_path:
        return get_last_close_from_csv(file_path)
    # Try to synthesize from inverse
    base, quote = pair[:3], pair[3:]
    inverse_pair = f"{quote}{base}"
    inverse_file_path = get_exported_csv(inverse_pair, start_date, end_date, export_dir)
    if inverse_file_path:
        inverse_close = get_last_close_from_csv(inverse_file_path)
        if inverse_close:
            return 1.0 / inverse_close
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--account_ccy', type=str, default=config.ACCOUNT_CCY, help='Account currency, e.g. USD')
    parser.add_argument('--lot_size', type=float, default=0.01, help='Lot size for pip value calculation (default 0.01)')
    parser.add_argument('--export_dir', type=str, default=config.EXPORT_DIR, help='Path to exported bar data directory')
    parser.add_argument('--lookback_days', type=int, default=getattr(config, 'CORRELATION_LOOKBACK_DAYS', 365), help='Lookback days for pip value date range')
    args = parser.parse_args()

    account_ccy = args.account_ccy.upper()
    lot_size = args.lot_size
    export_dir = args.export_dir
    lookback_days = args.lookback_days

    # Determine date range for file search (unified with batch_correlation_update)
    today = datetime.utcnow()
    start = today - timedelta(days=lookback_days)
    start_str = start.strftime('%Y.%m.%d')
    end_str = today.strftime('%Y.%m.%d')

    all_pairs = config.CCY_PAIRS

    # Step 1: For all needed conversion rates, get closing price for account_ccy/quote, using direct or synthesized
    needed_quotes = get_needed_quotes(all_pairs, account_ccy=account_ccy)
    usd_quote_prices = {}
    for quote in needed_quotes:
        price = get_or_synth_close(quote, start_str, end_str, export_dir)
        if price:
            usd_quote_prices[quote] = price
        else:
            print(f"[populate_pip_values] WARNING: Missing conversion rate for {quote} (and its inverse).")

    # Step 2: For each FX pair, calculate pip value using direct or synthesized close
    pip_value_records = []
    for pair in all_pairs:
        last_close = get_or_synth_close(pair, start_str, end_str, export_dir)
        if not last_close:
            print(f"[populate_pip_values] WARNING: No tickdata for {pair} and no inverse. Skipping.")
            continue
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
            print(f"[populate_pip_values] Error for {pair}: {e}")

    # Step 3: Insert/update into controller DB using config DB settings
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
    print(f"[populate_pip_values] Done populating pip values for lot size {lot_size}, account_ccy {account_ccy}!")

def pip_value_generic(pair, lot_size, pip_size, price, account_ccy, usd_quote_prices):
    quote_ccy = get_quote_ccy(pair)
    if quote_ccy == account_ccy:
        return lot_size * 100_000 * pip_size
    else:
        usd_quote = f"{account_ccy}{quote_ccy}"
        if usd_quote not in usd_quote_prices:
            raise ValueError(f"Missing conversion rate for {usd_quote}")
        return (lot_size * 100_000 * pip_size) / usd_quote_prices[usd_quote]

if __name__ == "__main__":
    main()