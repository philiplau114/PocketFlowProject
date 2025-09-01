import streamlit as st
import pandas as pd
import sqlalchemy
import redis
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from datetime import datetime, timedelta

# --- CONFIGURATION ---
if config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )
REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_QUEUE = config.REDIS_QUEUE

# --- DB & REDIS CONNECTIONS ---
engine = sqlalchemy.create_engine(DB_URL)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# --- STREAMLIT APP ---
st.set_page_config(page_title="Controller/Worker Monitoring Dashboard", layout="wide")
st.title("⚡ Controller/Worker Monitoring Dashboard")

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
    st.dataframe(df_aging)
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
    st.dataframe(df_chain)
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
    st.dataframe(df_recent)
else:
    st.info("No recent task activity found.")

st.caption("Refresh the page to update live data.")