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
                set_file_name,
                symbol,
                net_profit,
                max_drawdown,
                total_trades,
                recovery_factor,
                weighted_score,
                normalized_total_distance_to_good,
                win_rate,
                profit_factor,
                expected_payoff,
                criteria_passed as status,
                criteria_reason,
                created_at
            FROM v_test_metrics_scored
            ORDER BY net_profit DESC
            """,
            conn
        )
    return df

@st.cache_data(ttl=60)
def load_artifacts_for_task(link_id):
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT artifact_type, file_name, file_blob
            FROM controller_artifacts
            WHERE link_id = %s
              and link_type = "test_metrics"
            """,
            conn,
            params=(link_id,)
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
    "Rank", "set_file_name", "symbol", "net_profit", "max_drawdown",
    "total_trades", "recovery_factor", "weighted_score", "win_rate", "profit_factor",
    "expected_payoff", "status"
]
display_df = filtered[display_cols]
display_df = display_df.rename(columns={
    "set_file_name": "Strategy",
    "symbol": "Symbol",
    "net_profit": "Net Profit",
    "max_drawdown": "Max DD",
    "total_trades": "Total Trades",
    "recovery_factor": "Recovery Factor",
    "weighted_score": "Score",
    "win_rate": "Win Rate",
    "profit_factor": "Profit Factor",
    "expected_payoff": "Expected Payoff",
    "status": "Status",
})

# Conditional coloring and formatting
def color_net_profit(val):
    return "color: green;" if val > 0 else "color: red;"

def color_max_dd(val):
    return "color: red;" if val > 15 else "color: orange;" if val > 10 else "color: green;"

def color_score(val):
    return "color: green;" if val > 0.7 else "color: orange;" if val > 0.5 else "color: red;"

def color_win_rate(val):
    return "color: green;" if val > 60 else "color: orange;" if val > 50 else "color: red;"

styled_df = display_df.style.\
    applymap(color_net_profit, subset=["Net Profit"]).\
    applymap(color_max_dd, subset=["Max DD"]).\
    applymap(color_score, subset=["Score"]).\
    applymap(color_win_rate, subset=["Win Rate"])

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
        st.subheader(f"{strategy['set_file_name']}")

        st.caption(
            f"{strategy['symbol']} | Strategy ID: {strategy['metric_id']} | Created: {strategy['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        with st.container():
            # KPI Cards
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Net Profit", f"${strategy['net_profit']:.2f}")
            kpi2.metric("Max Drawdown", f"{strategy['max_drawdown']:.2f}")
            kpi3.metric("Total Trades", int(strategy['total_trades']))

            kpi4, kpi5, kpi6 = st.columns(3)
            kpi4.metric("Recovery Factor", f"{strategy['recovery_factor']:.2f}")
            kpi5.metric("Weighted Score", f"{strategy['weighted_score']:.2f}")
            kpi6.metric("Normalized Distance", f"{strategy['normalized_total_distance_to_good']:.2f}")

            kpi7, kpi8, kpi9 = st.columns(3)
            kpi7.metric("Win Rate", f"{strategy['win_rate']:.2f}%")
            kpi8.metric("Profit Factor", f"{strategy['profit_factor']:.2f}")
            kpi9.metric("Expected Payoff", f"{strategy['expected_payoff']:.2f}")

        # Criteria reason
        st.markdown(f"**Criteria Status:** {'✅' if strategy['status'] else '❌'} {strategy['criteria_reason']}")

        # --- Artifact Download and Graph ---
        # Use the metric_id (not task_id/controller_task_id) to fetch correct artifacts
        artifacts = load_artifacts_for_task(int(strategy["metric_id"]))

        # Flexible set file pick
        set_file_types_priority = [
            "output_set", "Best Pass set_file", "set_file", "ai_set", "input_set"
        ]
        set_file_row = pd.DataFrame()
        for typ in set_file_types_priority:
            set_file_row = artifacts[artifacts["artifact_type"] == typ]
            if not set_file_row.empty:
                break

        if not set_file_row.empty:
            set_file = set_file_row.iloc[0]
            if set_file["file_blob"] is not None:
                st.download_button(
                    label=f"Download {set_file['file_name']}",
                    data=set_file["file_blob"],
                    file_name=set_file["file_name"],
                    mime="application/octet-stream"
                )
            else:
                st.info("No .set file available for download (file is empty).")
        else:
            st.info("No .set file available for download.")

        # Flexible gif pick
        gif_types_priority = [
            "output_gif", "optimization_report_gif", "input_gif"
        ]
        gif_row = pd.DataFrame()
        for typ in gif_types_priority:
            gif_row = artifacts[artifacts["artifact_type"] == typ]
            if not gif_row.empty:
                break

        if not gif_row.empty:
            gif = gif_row.iloc[0]
            if gif["file_blob"] is not None:
                st.image(BytesIO(gif["file_blob"]), caption=gif["file_name"], use_column_width=True)
            else:
                st.info("No equity curve available (file is empty).")
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