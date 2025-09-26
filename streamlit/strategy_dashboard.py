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
from session_manager import is_authenticated, sync_streamlit_session

# --- CONFIG ---
if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )

engine = sqlalchemy.create_engine(DB_URL)
r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)

# --- Session Check ---
if not is_authenticated(st.session_state):
    st.warning("You must be logged in to view this page.")
    st.stop()
sync_streamlit_session(st.session_state, st.session_state["username"])

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
    key = st.session_state.get("open_router_api_key")
    if key:
        return key
    username = st.session_state.get("username")
    if username:
        val = r.get(f"user:{username}:open_router_api_key")
        if val:
            return val
    return None

def call_open_router_api(set_file_blob, summary_metrics_blob, user_api_key):
    with open(os.path.join(os.path.dirname(__file__), "explain_set.md"), "r") as f:
        prompt_template = f.read()
    set_file_str = set_file_blob.decode() if isinstance(set_file_blob, bytes) else set_file_blob
    summary_csv_str = summary_metrics_blob.decode() if isinstance(summary_metrics_blob, bytes) else summary_metrics_blob
    prompt = prompt_template.replace("Here is the .set file:", f"Here is the .set file:\n\n{set_file_str}\n\n")
    prompt = prompt.replace("And here is the backtest summary (.csv):", f"And here is the backtest summary (.csv):\n\n{summary_csv_str}\n\n")
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
        try:
            ai_content = result["choices"][0]["message"]["content"]
        except Exception:
            ai_content = "Failed to parse AI response."
        return ai_content
    else:
        return f"Error from OpenRouter: {response.status_code} - {response.text}"

# --- UI Layout ---
st.set_page_config(page_title="Strategy Dashboard", layout="wide")

# Custom CSS: make main content always full width
st.markdown(
    """
    <style>
    .block-container { max-width: 100% !important; padding: 2rem 2rem 2rem 2rem; }
    .element-container { width: 100% !important; }
    .stDataFrame, .stSelectbox, .stDataEditor { width: 100% !important; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("📈 Strategy Dashboard")

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

# ---- User-defined records per page ----
st.subheader("Strategies")
max_page_size = min(50, len(display_df))
page_size = st.number_input("Records per page", min_value=1, max_value=max_page_size if max_page_size > 0 else 1, value=3, step=1)

num_pages = max((len(display_df) - 1) // page_size + 1, 1)
page_num = st.number_input("Page", min_value=1, max_value=num_pages, value=1, step=1)
start_idx = (page_num - 1) * page_size
end_idx = start_idx + page_size
paged_df = display_df.iloc[start_idx:end_idx].reset_index(drop=True)

# --- Dynamic column width for Strategy (st.data_editor only) ---
if not paged_df.empty:
    max_strategy_len = paged_df["Strategy"].map(len).max()
else:
    max_strategy_len = 20
strategy_col_width = min(max(200, max_strategy_len * 9), 600)  # Estimate width

st.data_editor(
    paged_df,
    width="stretch",
    hide_index=True,
    column_config={"Strategy": st.column_config.Column(width=strategy_col_width)},
    disabled=True,
    key="strategy_table_view"
)

strategy_names = paged_df["Strategy"].tolist()
selected_name = st.selectbox("Select strategy for details", strategy_names)
selected_idx = None
if selected_name:
    sel_row = paged_df[paged_df["Strategy"] == selected_name].index[0]
    selected_idx = start_idx + sel_row

if selected_idx is not None and 0 <= selected_idx < len(filtered):
    strategy = filtered.iloc[selected_idx]
    st.markdown(f"## {strategy['set_file_name']}")
    st.caption(f"{strategy['symbol']} | Strategy ID: {strategy['metric_id']} | Created: {strategy['created_at'].strftime('%Y-%m-%d %H:%M')}")
    with st.container():
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

    st.markdown(f"**Criteria Status:** {'✅' if strategy['status'] else '❌'} {strategy['criteria_reason']}")

    artifacts = load_artifacts_for_task(int(strategy["metric_id"]))

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
            st.image(BytesIO(gif["file_blob"]), caption=gif["file_name"], width="stretch")
        else:
            st.info("No equity curve available (file is empty).")
    else:
        st.info("No equity curve available.")

    set_file_summary_row = artifacts[artifacts["artifact_type"] == "set_file_summary"]
    summary_shown_key = f"ai_summary_shown_{strategy['metric_id']}"
    summary_md = None
    if not set_file_summary_row.empty:
        summary_md = set_file_summary_row.iloc[0]["file_blob"]
        if isinstance(summary_md, bytes):
            summary_md = summary_md.decode()
        st.session_state[summary_shown_key] = True
        st.markdown("### AI Set File Summary")
        st.markdown(summary_md, unsafe_allow_html=True)
    else:
        if st.session_state.get(summary_shown_key, False) and st.session_state.get(f"last_ai_summary_{strategy['metric_id']}", None):
            summary_md = st.session_state[f"last_ai_summary_{strategy['metric_id']}"]
            st.markdown("### AI Set File Summary")
            st.markdown(summary_md, unsafe_allow_html=True)

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
                    st.session_state[summary_shown_key] = True
                    st.session_state[f"last_ai_summary_{strategy['metric_id']}"] = ai_summary
                    st.markdown("### AI Set File Summary")
                    st.markdown(ai_summary)
                except Exception as e:
                    st.error(f"Failed to save summary: {e}")
            else:
                st.error("Failed to generate AI Set File Summary.")
else:
    if len(display_df) == 0:
        st.warning("No strategy data available.")
    else:
        st.info("Select a strategy from the table above to view details.")

st.caption("Do not sell or share your personal info")