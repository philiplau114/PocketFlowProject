import streamlit as st
import pandas as pd
import sqlalchemy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import redis
from io import BytesIO

# --- CONFIG ---
if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )
REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_QUEUE = config.REDIS_QUEUE

engine = sqlalchemy.create_engine(DB_URL)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# --- Load Data ---
@st.cache_data(ttl=60)
def load_metrics():
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT 
                id as metric_id,
                set_file_name,          -- strategy name
                symbol,
                net_profit,
                profit_factor,
                expected_payoff,
                total_trades,
                max_drawdown_pct,       -- note: not 'max_drawdown_percent'
                profit_trades_pct,
                criteria_passed as status,
                controller_task_id as task_id,
                created_at
            FROM v_test_metrics_scored
            ORDER BY net_profit DESC
            """,
            conn
        )
    return df

@st.cache_data(ttl=60)
def load_artifacts_for_task(task_id):
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT artifact_type, artifact_name, artifact_blob
            FROM controller_artifacts
            WHERE controller_task_id = %s
            """,
            conn,
            params=(task_id,)
        )
    return df

# --- UI Layout ---
st.set_page_config(page_title="Strategy Dashboard", layout="wide")
st.markdown(
    """
    <style>
    .big-font {font-size:20px !important;}
    .strategy-table thead tr th {font-size:16px;}
    </style>
    """, unsafe_allow_html=True
)
st.title("📈 Strategy Dashboard")

# --- Strategy Search and Table ---
metrics_df = load_metrics()
search = st.text_input("Search strategies...", "")

if search:
    filtered = metrics_df[metrics_df["set_file_name"].str.contains(search, case=False, na=False)]
else:
    filtered = metrics_df

filtered = filtered.reset_index(drop=True)
filtered['Rank'] = filtered.index + 1

display_cols = [
    "Rank", "set_file_name", "symbol", "net_profit", "profit_factor", "expected_payoff",
    "total_trades", "max_drawdown_pct", "profit_trades_pct", "status"
]
display_df = filtered[display_cols]
display_df = display_df.rename(columns={
    "set_file_name": "Strategy",
    "symbol": "Symbol",
    "net_profit": "Net Profit",
    "profit_factor": "Profit Factor",
    "expected_payoff": "Expected Payoff",
    "total_trades": "Total Trades",
    "max_drawdown_pct": "Max DD (%)",
    "profit_trades_pct": "Profit Trades (%)",
    "status": "Status"
})

# Conditional coloring and formatting
def color_net_profit(val):
    return "color: green;" if val > 0 else "color: red;"

def color_max_dd(val):
    return "color: red;" if val > 15 else "color: orange;" if val > 10 else "color: green;"

def color_profit_trades(val):
    return "color: green;" if val > 60 else "color: orange;" if val > 50 else "color: red;"

styled_df = display_df.style.\
    applymap(color_net_profit, subset=["Net Profit"]).\
    applymap(color_max_dd, subset=["Max DD (%)"]).\
    applymap(color_profit_trades, subset=["Profit Trades (%)"])

col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Strategies")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    if len(filtered) > 0:
        selected_idx = st.number_input(
            "Select strategy rank for detail", min_value=1, max_value=len(filtered), value=1, step=1
        ) - 1
    else:
        selected_idx = None

with col2:
    if selected_idx is not None and len(filtered) > 0:
        strategy = filtered.iloc[selected_idx]
        st.subheader(f"{strategy['Strategy']}")

        st.caption(f"{strategy['Symbol']} | Task ID: {strategy['task_id']} | Created: {strategy['created_at'].strftime('%Y-%m-%d %H:%M')}")
        with st.container():
            # KPI Cards
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Net Profit", f"${strategy['Net Profit']:.2f}")
            kpi2.metric("Profit Factor", f"{strategy['Profit Factor']:.2f}")
            kpi3.metric("Expected Payoff", f"{strategy['Expected Payoff']:.2f}")

            kpi4, kpi5, kpi6 = st.columns(3)
            kpi4.metric("Total Trades", int(strategy['Total Trades']))
            kpi5.metric("Max Drawdown", f"{strategy['Max DD (%)']:.2f}%")
            kpi6.metric("Profit Trades", f"{strategy['Profit Trades (%)']:.2f}%")
        
        # --- Artifact Download and Graph ---
        artifacts = load_artifacts_for_task(strategy["task_id"])
        set_file_row = artifacts[artifacts["artifact_type"] == "set_file"]
        gif_row = artifacts[artifacts["artifact_type"].str.contains("gif")]

        if not set_file_row.empty:
            set_file = set_file_row.iloc[0]
            st.download_button(
                label="Download .set file",
                data=set_file["artifact_blob"],
                file_name=set_file["artifact_name"],
                mime="application/octet-stream"
            )
        else:
            st.info("No .set file available for download.")

        if not gif_row.empty:
            gif = gif_row.iloc[0]
            st.image(BytesIO(gif["artifact_blob"]), caption="Equity Curve", use_column_width=True)
        else:
            st.info("No equity curve available.")

        # --- Lot size recommendations (example static) ---
        st.markdown("### AI Lot Size Recommendation")
        lot1, lot2, lot3 = st.columns(3)
        lot1.metric("Low Risk", "0.10 lots")
        lot2.metric("Medium Risk", "0.05 lots")
        lot3.metric("Full Risk", "0.20 lots")
        st.success("Suggestion: Increase. Low drawdown indicates potential for higher lot sizes.")

    else:
        st.warning("No strategy data available.")

st.caption("Do not sell or share your personal info")