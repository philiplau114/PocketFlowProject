import streamlit as st
import pandas as pd
import sqlalchemy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import redis
from datetime import datetime, timedelta
from session_manager import is_authenticated, sync_streamlit_session

# --- CONFIGURATION ---
if config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )

engine = sqlalchemy.create_engine(DB_URL)
r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
REDIS_QUEUE = config.REDIS_QUEUE

# --- STREAMLIT APP ---
st.set_page_config(page_title="Controller/Worker Monitoring Dashboard", layout="wide")
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
st.title("⚡ Controller/Worker Monitoring Dashboard")

# --- Session Check (reuse session per user) ---
if not is_authenticated(st.session_state):
    st.warning("You must be logged in as an Admin to view this page.")
    st.stop()
sync_streamlit_session(st.session_state, st.session_state["username"])

# --- THRESHOLDS MANAGEMENT ---
st.header("Threshold Management")

with engine.connect() as conn:
    # Try to read thresholds from DB
    try:
        df_thresh = pd.read_sql("SELECT name, value FROM controller_thresholds", conn)
    except Exception as e:
        df_thresh = pd.DataFrame()
        st.warning(f"Could not read controller_thresholds table: {e}")

    if not df_thresh.empty:
        st.subheader("Current Thresholds (Editable)")
        thresh_updates = {}
        cols = st.columns(len(df_thresh))
        for i, row in enumerate(df_thresh.itertuples()):
            thresh_updates[row.name] = cols[i].number_input(
                f"{row.name}", value=float(row.value), key=f"thresh_{row.name}", step=0.01
            )
        if st.button("Update Thresholds"):
            for name, value in thresh_updates.items():
                conn.execute(
                    sqlalchemy.text("UPDATE controller_thresholds SET value = :value WHERE name = :name"),
                    {"value": value, "name": name}
                )
            st.success("Thresholds updated! Please refresh the page to see changes.")
    else:
        st.info("No dynamic thresholds found. Using .env.controller values.")
        st.write({
            "MAX_ATTEMPTS": config.TASK_MAX_ATTEMPTS,
            "MAX_FINE_TUNE_DEPTH": config.MAX_FINE_TUNE_DEPTH,
            "DISTANCE_THRESHOLD": config.DISTANCE_THRESHOLD,
            "SCORE_THRESHOLD": config.SCORE_THRESHOLD,
            "AGING_FACTOR": config.AGING_FACTOR,
        })

st.markdown("---")

# --- TASK STATUS OVERVIEW ---
st.header("Task Status Overview")
with engine.connect() as conn:
    df_status = pd.read_sql(
        "SELECT status, COUNT(*) AS count FROM controller_tasks GROUP BY status", conn
    )
if not df_status.empty:
    st.bar_chart(df_status.set_index("status"))
else:
    st.info("No task data found in the database.")

# --- QUEUE DEPTH ---
queue_depth = r.llen(REDIS_QUEUE)
st.metric("Redis Queue Depth", queue_depth)

# --- AGING/WAIT TIME ---
st.header("Task Aging / Wait Time")
with engine.connect() as conn:
    df_aging = pd.read_sql(
        """
        SELECT id, status, attempt_count, created_at, updated_at, 
               TIMESTAMPDIFF(MINUTE, created_at, NOW()) as wait_mins
        FROM controller_tasks 
        WHERE status = 'new' OR status = 'retrying'
        ORDER BY wait_mins DESC
        LIMIT 20
        """,
        conn,
    )
if not df_aging.empty:
    st.data_editor(df_aging, width="stretch", hide_index=True, disabled=True)
    starved = df_aging[df_aging['wait_mins'] > 60]
    if not starved.empty:
        st.warning(f"⚠️ {len(starved)} tasks have been waiting over 60 minutes!")
else:
    st.info("No new or retrying tasks waiting.")

# --- FINE-TUNE/RETRY CHAINS ---
st.header("Fine-Tune / Retry Chains")
with engine.connect() as conn:
    df_chain = pd.read_sql(
        """
        SELECT id, parent_task_id, fine_tune_depth, attempt_count, status, updated_at
        FROM controller_tasks
        WHERE fine_tune_depth > 0 OR attempt_count > 1
        ORDER BY updated_at DESC LIMIT 30
        """,
        conn,
    )
if not df_chain.empty:
    st.data_editor(df_chain, width="stretch", hide_index=True, disabled=True)
else:
    st.info("No fine-tune or retry chains found.")

# --- FAILURE/ATTEMPT RATES ---
st.header("Completions, Failures, Retries (Last 14 days)")
with engine.connect() as conn:
    df_result = pd.read_sql(
        """
        SELECT DATE(updated_at) as day, status, COUNT(*) as count
        FROM controller_tasks
        WHERE updated_at > CURDATE() - INTERVAL 14 DAY
        GROUP BY day, status
        """,
        conn,
    )
if not df_result.empty:
    pivot = df_result.pivot(index="day", columns="status", values="count").fillna(0)
    st.line_chart(pivot)
else:
    st.info("No recent completion/failure/retry data.")

# --- RECENT ACTIVITY ---
st.header("Recent Task Activity")
with engine.connect() as conn:
    df_recent = pd.read_sql(
        """
        SELECT 
            ct.id, 
            ct.status, 
            ct.attempt_count, 
            ct.fine_tune_depth, 
            vtm.weighted_score, 
            vtm.normalized_total_distance_to_good, 
            ct.last_error, 
            ct.updated_at
        FROM controller_tasks ct
        LEFT JOIN v_test_metrics_scored vtm ON vtm.controller_task_id = ct.id
        ORDER BY ct.updated_at DESC LIMIT 20
        """,
        conn,
    )
if not df_recent.empty:
    st.data_editor(df_recent, width="stretch", hide_index=True, disabled=True)
else:
    st.info("No recent task activity found.")

st.caption("Refresh the page to update live data.")