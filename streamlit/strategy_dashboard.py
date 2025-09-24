import streamlit as st
import pandas as pd
import sqlalchemy
import sys
import os
from io import BytesIO
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_utils import get_db, store_set_file_summary
import config
import redis

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

def get_open_router_api_key():
    # Try to get user's open_router_api_key from session or Redis
    key = st.session_state.get("open_router_api_key")
    if key:
        return key
    # If not in session, try to get from Redis using username
    username = st.session_state.get("username")
    if username:
        val = r.get(f"user:{username}:open_router_api_key")
        if val:
            return val
    return None

def call_open_router_api(set_file_blob, summary_metrics_blob, user_api_key):
    # Compose the prompt markdown using the template in explain_set.md
    # For simplicity, assume explain_set.md is in the same directory
    with open(os.path.join(os.path.dirname(__file__), "explain_set.md"), "r") as f:
        prompt_template = f.read()
    set_file_str = set_file_blob.decode() if isinstance(set_file_blob, bytes) else set_file_blob
    summary_csv_str = summary_metrics_blob.decode() if isinstance(summary_metrics_blob, bytes) else summary_metrics_blob
    prompt = prompt_template.replace("Here is the .set file:", f"Here is the .set file:\n\n{set_file_str}\n\n")
    prompt = prompt.replace("And here is the backtest summary (.csv):", f"And here is the backtest summary (.csv):\n\n{summary_csv_str}\n\n")
    # Call OpenRouter API
    import requests
    headers = {
        "Authorization": f"Bearer {user_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        # Extract AI response (assume OpenRouter compatible with OpenAI schema)
        try:
            ai_content = result["choices"][0]["message"]["content"]
        except Exception:
            ai_content = "Failed to parse AI response."
        return ai_content
    else:
        return f"Error from OpenRouter: {response.status_code} - {response.text}"

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
    "expected_payoff", "normalized_total_distance_to_good", "status"
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
    "normalized_total_distance_to_good": "Distance",
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

def color_distance(val):
    return "color: green;" if val < 0.5 else "color: orange;" if val < 1.0 else "color: red;"

styled_df = display_df.style.\
    map(color_net_profit, subset=["Net Profit"]).\
    map(color_max_dd, subset=["Max DD"]).\
    map(color_score, subset=["Score"]).\
    map(color_win_rate, subset=["Win Rate"]).\
    map(color_distance, subset=["Distance"])

col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Strategies")
    st.dataframe(styled_df, width='stretch', hide_index=True)
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
            kpi6.metric("Distance", f"{strategy['normalized_total_distance_to_good']:.2f}")

            kpi7, kpi8, kpi9 = st.columns(3)
            kpi7.metric("Win Rate", f"{strategy['win_rate']:.2f}%")
            kpi8.metric("Profit Factor", f"{strategy['profit_factor']:.2f}")
            kpi9.metric("Expected Payoff", f"{strategy['expected_payoff']:.2f}")

        # Criteria reason
        st.markdown(f"**Criteria Status:** {'✅' if strategy['status'] else '❌'} {strategy['criteria_reason']}")

        # --- Artifact Download and Graph ---
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
                st.image(BytesIO(gif["file_blob"]), caption=gif["file_name"], width='stretch')
            else:
                st.info("No equity curve available (file is empty).")
        else:
            st.info("No equity curve available.")

        # --- Set File Summary / AI Set Summary Button Logic ---
        set_file_summary_row = artifacts[artifacts["artifact_type"] == "set_file_summary"]
        # Determine if summary is already generated or just generated this session
        summary_shown_key = f"ai_summary_shown_{strategy['metric_id']}"
        summary_md = None
        if not set_file_summary_row.empty:
            summary_md = set_file_summary_row.iloc[0]["file_blob"]
            if isinstance(summary_md, bytes):
                summary_md = summary_md.decode()
            # Mark as shown in session state to disable button
            st.session_state[summary_shown_key] = True
            st.markdown("### AI Set File Summary")
            st.markdown(summary_md, unsafe_allow_html=True)
        else:
            # If just generated this session, get it from session and show
            if st.session_state.get(summary_shown_key, False) and st.session_state.get(f"last_ai_summary_{strategy['metric_id']}", None):
                summary_md = st.session_state[f"last_ai_summary_{strategy['metric_id']}"]
                st.markdown("### AI Set File Summary")
                st.markdown(summary_md, unsafe_allow_html=True)

        # Button logic (disable if summary shown)
        user_api_key = get_open_router_api_key()
        output_set_row = artifacts[artifacts["artifact_type"] == "output_set"]
        summary_metrics_csv_row = artifacts[artifacts["artifact_type"] == "summary_metrics_csv"]
        enable_button = user_api_key and not output_set_row.empty and not summary_metrics_csv_row.empty
        disable_btn = st.session_state.get(summary_shown_key, False)
        btn = st.button(
            "Generate AI Set Summary",
            disabled=not enable_button or disable_btn,
            key=f"gen_ai_summary_btn_{strategy['metric_id']}"
        )
        if not enable_button:
            st.info("To enable: store your OpenRouter API key in your profile and make sure output_set and summary_metrics_csv are available.")

        # Button click logic - only runs if not disabled
        if btn and enable_button and not disable_btn:
            with st.spinner("Generating AI summary via OpenRouter..."):
                set_file_blob = output_set_row.iloc[0]["file_blob"]
                summary_metrics_blob = summary_metrics_csv_row.iloc[0]["file_blob"]
                ai_summary = call_open_router_api(set_file_blob, summary_metrics_blob, user_api_key)
                if ai_summary:
                    session = get_db()
                    try:
                        store_set_file_summary(session, int(strategy["metric_id"]), ai_summary)
                        st.success("Set file summary saved!")
                        # Mark as shown and store last summary in session state
                        st.session_state[summary_shown_key] = True
                        st.session_state[f"last_ai_summary_{strategy['metric_id']}"] = ai_summary
                        st.markdown("### AI Set File Summary")
                        st.markdown(ai_summary)
                    except Exception as e:
                        st.error(f"Failed to save summary: {e}")
                else:
                    st.error("Failed to generate AI Set File Summary.")

    else:
        st.warning("No strategy data available.")

st.caption("Do not sell or share your personal info")