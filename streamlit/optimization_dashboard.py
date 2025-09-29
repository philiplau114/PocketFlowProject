import streamlit as st
import pandas as pd
import sqlalchemy
import os
import json
from datetime import datetime
from io import StringIO

# --- CONFIG ---
from db_utils import get_db, extract_setfile_metadata
import config

# Database connection
if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )
engine = sqlalchemy.create_engine(DB_URL)

st.set_page_config(page_title="Job & Strategy Dashboard", layout="wide")
st.title("📋 Job & Strategy Dashboard")

# --- Utility: Load jobs and strategies ---
@st.cache_data(ttl=60)
def load_jobs(user_id_filter=None, status_filter=None):
    query = """
    SELECT
        jobs.id as job_id,
        jobs.user_id,
        jobs.ea_name,
        jobs.symbol,
        jobs.timeframe,
        jobs.original_file,
        jobs.status,
        jobs.created_at,
        jobs.updated_at,
        tasks.id as task_id,
        tasks.status as task_status,
        metrics.id as strategy_id,
        metrics.set_file_name,
        metrics.net_profit,
        metrics.weighted_score,
        metrics.total_trades,
        metrics.max_drawdown,
        metrics.win_rate
    FROM controller_jobs jobs
    LEFT JOIN controller_tasks tasks ON tasks.job_id = jobs.id
    LEFT JOIN v_test_metrics_scored metrics ON metrics.controller_task_id = tasks.id
    WHERE 1=1
    """
    if user_id_filter:
        query += f" AND jobs.user_id = '{user_id_filter}'"
    if status_filter:
        query += f" AND jobs.status = '{status_filter}'"
    query += " ORDER BY jobs.created_at DESC, jobs.id DESC"
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

# --- Upload Section ---
st.header("Upload New .set File")
uploaded_file = st.file_uploader("Upload a .set file", type=["set"])

if uploaded_file is not None:
    file_content = uploaded_file.read().decode(errors="ignore")
    fields = extract_setfile_metadata(StringIO(file_content))
    ea_name = fields.get("EA", "")
    symbol = fields.get("Symbol", "")
    timeframe = fields.get("Timeframe", "")
    st.write("**Extracted Metadata:**")
    st.json({"EA Name": ea_name, "Symbol": symbol, "Timeframe": timeframe})
    user_id = st.session_state.get("username", None)  # <-- Get current user id from session
    if not ea_name or not symbol or not timeframe or not user_id:
        st.warning("Could not extract all required metadata or user not logged in. Please check the .set file content and make sure you are logged in.")
    else:
        if st.button("Confirm and Upload"):
            # Save .set file to WATCH_FOLDER for controller to pick up
            save_path = os.path.join(config.WATCH_FOLDER, uploaded_file.name)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            # Save metadata sidecar file (.meta.json) with user_id, symbol, timeframe, ea_name, original_filename
            meta_data = {
                "user_id": user_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "ea_name": ea_name,
                "original_filename": uploaded_file.name
            }
            meta_path = save_path + ".meta.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f)
            st.success(f"File {uploaded_file.name} uploaded and queued for job creation.")
            st.info("Controller will process the file and create the job automatically using your user ID and extracted metadata.")

st.markdown("---")

# --- Job/Strategy Table Section ---
st.header("All Jobs & Strategies")
# Filter by user and status
with st.expander("Filters"):
    user_id_filter = st.text_input("Filter by User ID (leave blank for all)", "")
    status_filter = st.selectbox("Filter by Job Status", ["", "NEW", "QUEUED", "WORKER_COMPLETED", "WORKER_FAILED", "COMPLETED_SUCCESS", "COMPLETED_PARTIAL", "FAILED"])
    filter_btn = st.button("Apply Filter")

# Load jobs
jobs_df = load_jobs(user_id_filter=user_id_filter if filter_btn or user_id_filter else None,
                    status_filter=status_filter if filter_btn and status_filter else None)

if jobs_df.empty:
    st.info("No jobs found.")
else:
    # Prepare table
    display_cols = [
        "job_id", "user_id", "ea_name", "symbol", "timeframe", "original_file",
        "status", "created_at", "updated_at", "strategy_id", "set_file_name",
        "net_profit", "weighted_score", "total_trades", "max_drawdown", "win_rate"
    ]
    jobs_df_display = jobs_df[display_cols].drop_duplicates().fillna("")
    jobs_df_display = jobs_df_display.rename(columns={
        "job_id": "Job ID",
        "user_id": "User ID",
        "ea_name": "EA Name",
        "symbol": "Symbol",
        "timeframe": "Timeframe",
        "original_file": "Set File",
        "status": "Job Status",
        "created_at": "Created At",
        "updated_at": "Updated At",
        "strategy_id": "Strategy ID",
        "set_file_name": "Strategy File",
        "net_profit": "Net Profit",
        "weighted_score": "Score",
        "total_trades": "Trades",
        "max_drawdown": "Max DD",
        "win_rate": "Win Rate (%)"
    })
    st.dataframe(jobs_df_display, use_container_width=True)

    # --- Re-optimization Section ---
    st.subheader("Re-Optimize Strategy")
    selectable = jobs_df_display[jobs_df_display["Strategy ID"] != ""]
    strat_ids = selectable["Strategy ID"].unique()
    if len(strat_ids) == 0:
        st.info("No re-optimizable strategies found.")
    else:
        selected_strat = st.selectbox("Select a Strategy to Re-Optimize", [""] + list(strat_ids))
        if selected_strat:
            # Show details
            strat_row = selectable[selectable["Strategy ID"] == selected_strat].iloc[0]
            st.write(f"**Strategy:** {strat_row['Strategy File']} | **Symbol:** {strat_row['Symbol']} | **EA:** {strat_row['EA Name']}")
            st.write(f"**Job ID:** {strat_row['Job ID']} | **Set File:** {strat_row['Set File']}")
            if st.button("Trigger Re-Optimization"):
                # Call stored procedure: reoptimize_job(selected_strat)
                with engine.connect() as conn:
                    conn.execute(f"CALL reoptimize_job({int(selected_strat)});")
                st.success("Re-optimization triggered. Controller will handle the job.")

st.caption("This dashboard allows you to manage, upload, and re-optimize strategies. For admin or advanced controls, contact support.")

# --- END OF FILE ---