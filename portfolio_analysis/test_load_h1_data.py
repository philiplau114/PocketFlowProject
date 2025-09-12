import os
import pandas as pd

EXPORT_DIR = "test_exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

csv_content = """Date,Time,Open,High,Low,Close,Tick volume
2024.09.09,00:00:00,1.10864,1.1091,1.10823,1.10832,2104
2024.09.09,01:00:00,1.10831,1.10909,1.10813,1.1082,3273
"""

pair = "EURUSD"
start_date = "2024.09.09"
end_date = "2024.09.09"
file_name = f"Dukascopy-{pair}-{start_date}-{end_date}-bardata_H1.csv"
file_path = os.path.join(EXPORT_DIR, file_name)
with open(file_path, "w") as f:
    f.write(csv_content)

def load_h1_data(pair, start_date, end_date):
    file_name = f"Dukascopy-{pair}-{start_date}-{end_date}-bardata_H1.csv"
    file_path = os.path.join(EXPORT_DIR, file_name)
    df = pd.read_csv(file_path, sep=",")
    df.columns = df.columns.str.strip()
    df['datetime'] = pd.to_datetime(df['Date'] + " " + df['Time'])
    df.set_index('datetime', inplace=True)
    return df['Close']

def test_load_h1_data():
    close_series = load_h1_data(pair, start_date, end_date)
    assert len(close_series) == 2
    assert close_series.iloc[0] == 1.10832
    assert close_series.iloc[1] == 1.1082
    print(close_series)