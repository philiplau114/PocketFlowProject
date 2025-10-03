import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import os
import json
from datetime import datetime
import hashlib

# --- CONFIG ---
from db_utils import extract_setfile_metadata
import config
import session_manager

# --- SHARED RE-OPTIMIZE LOGIC ---
from reoptimize_utils import reoptimize_by_metric  # Shared utility at project root

# --- Status Constants ---
from db.status_constants import (
    JOB_STATUS_NEW,
    JOB_STATUS_QUEUED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_COMPLETED_SUCCESS,
    JOB_STATUS_COMPLETED_PARTIAL,
    JOB_STATUS_FAILED,
)

ALLOWED_REOPTIMIZE_STATUSES = [
    JOB_STATUS_COMPLETED_SUCCESS,
    JOB_STATUS_COMPLETED_PARTIAL,
    JOB_STATUS_FAILED,
]

if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )
engine = sqlalchemy.create_engine(DB_URL)

st.set_page_config(page_title="Job & Strategy Dashboard", layout="wide")

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
st.title("📋 Job & Strategy Dashboard")

# --- Streamlit session sync with Redis session ---
if "username" in st.session_state:
    session_manager.sync_streamlit_session(st.session_state, st.session_state["username"])

@st.cache_data(ttl=60)
def load_jobs(user_name=None, status=None):
    query = """
    SELECT * FROM (
        SELECT 
            controller_jobs.id,
            (SELECT username FROM users WHERE id = controller_jobs.user_id) AS user,
            controller_jobs.symbol,
            controller_jobs.timeframe,
            controller_jobs.ea_name,
            controller_jobs.original_file,
            controller_jobs.status,
            controller_jobs.created_at,
            task_summary.number_of_attempt,
            task_summary.number_of_refine,
            task_summary.latest_update
        FROM
            trading_optimization.controller_jobs,
            (SELECT 
                job_id,
                    SUM(attempt_count) AS number_of_attempt,
                    MAX(fine_tune_depth) AS number_of_refine,
                    MAX(last_heartbeat) AS latest_update
            FROM
                controller_tasks
            GROUP BY job_id) task_summary
        WHERE
            controller_jobs.id = task_summary.job_id
    ) jobs
    WHERE (%s IS NULL OR user = %s)
      AND (%s IS NULL OR status = %s)
    ORDER BY created_at DESC, id DESC
    """
    params = (user_name, user_name, status, status)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    return df

@st.cache_data(ttl=30)
def load_details(job_id: int):
    query = """
    SELECT 
        metrics.id AS metric_id,
        metrics.set_file_name,
        metrics.symbol,
        metrics.start_date,
        metrics.end_date,
        metrics.net_profit,
        metrics.max_drawdown,
        metrics.total_trades,
        metrics.recovery_factor,
        metrics.win_rate,
        metrics.profit_factor,
        metrics.expected_payoff,
        metrics.criteria_passed,
        metrics.criteria_reason,
        metrics.weighted_score,
        metrics.normalized_total_distance_to_good,
        metrics.created_at
    FROM
        controller_tasks tasks,
        v_test_metrics_scored metrics
    WHERE
        metrics.controller_task_id = tasks.id
            AND metrics.id IS NOT NULL
            AND tasks.job_id = %s
    ORDER BY metrics.normalized_total_distance_to_good , metrics.weighted_score DESC
    """
    with engine.connect() as conn:
        details = pd.read_sql(query, conn, params=(int(job_id),))
    return details

def file_exists_in_active_jobs_or_tasks(engine, input_file_name):
    sql = """
    SELECT 
        jobs.exist_in_jobs + tasks.exist_in_tasks as file_existed
    FROM
        (SELECT 
            COUNT(*) AS exist_in_jobs
        FROM
            controller_jobs
        WHERE
            SUBSTRING_INDEX(original_file, '\\\\', -1) = :param1
            AND status NOT IN ('completed_success', 'completed_partial', 'failed')
        ) jobs,
        (SELECT 
            COUNT(*) AS exist_in_tasks
        FROM
            trading_optimization.controller_tasks
        WHERE
            SUBSTRING_INDEX(file_path, '\\\\', -1) = :param2
            AND status NOT IN ('completed_success', 'completed_partial', 'failed')
        ) tasks;
    """
    try:
        with engine.connect() as conn:
            res = conn.execute(text(sql), {"param1": input_file_name, "param2": input_file_name})
            row = res.fetchone()
            if row and row[0] > 0:
                return True
        return False
    except Exception as e:
        st.error(f"Database error in file_exists_in_active_jobs_or_tasks: {e}")
        return False

if 'is_reoptimizing' not in st.session_state:
    st.session_state['is_reoptimizing'] = False
if 'reopt_args' not in st.session_state:
    st.session_state['reopt_args'] = None
if 'reopt_message' not in st.session_state:
    st.session_state['reopt_message'] = ""

if st.session_state['is_reoptimizing']:
    with st.spinner("Re-optimization in progress... Please wait."):
        if st.session_state['reopt_args'] is not None:
            try:
                # Direct call with explicit arguments, no unpacking
                reopt_args = st.session_state['reopt_args']
                reoptimize_by_metric(
                    engine=engine,
                    metric_id=reopt_args['metric_id'],
                    job_row=reopt_args['job_row'],
                    metric_row=reopt_args['metric_row'],
                    user_id=reopt_args['user_id'],
                    watch_folder=config.WATCH_FOLDER,
                    prefix="R"
                )
                st.session_state['reopt_message'] = "Re-optimization complete! (see watch folder)"
            except Exception as e:
                st.session_state['reopt_message'] = f"Failed to trigger re-optimization: {e}"
            st.session_state['reopt_args'] = None
        st.session_state['is_reoptimizing'] = False
        st.rerun()

if st.session_state.get('reopt_message'):
    if "Failed" in st.session_state['reopt_message']:
        st.error(st.session_state['reopt_message'])
    else:
        st.success(st.session_state['reopt_message'])
    st.session_state['reopt_message'] = ""

# --- Upload Section ---
st.header("Upload New .set File")
st.caption("File size limit: 100KB (.set files only)")
MAX_FILE_SIZE = 100 * 1024  # 100KB
uploaded_file = st.file_uploader("Upload a .set file", type=["set"])
if uploaded_file:
    try:
        if uploaded_file.size > MAX_FILE_SIZE:
            st.error("File size exceeds 100KB limit. Please upload a smaller .set file.")
        else:
            raw_bytes = uploaded_file.read()
            fields = extract_setfile_metadata(uploaded_file.name)
            ea_name = str(fields.get("ea_name", "")).strip()
            symbol = str(fields.get("symbol", "")).strip()
            timeframe = str(fields.get("timeframe", "")).strip()

            st.write("**Extracted Metadata:**")
            st.json({
                "EA Name": ea_name,
                "Symbol": symbol,
                "Timeframe": timeframe
            })

            user_id = st.session_state.get("user_id", None)

            if not ea_name or not symbol or not timeframe or user_id is None:
                st.warning("Could not extract all required metadata or user not logged in. Please check the .set file content and make sure you are logged in.")
            else:
                input_file_name = os.path.basename(uploaded_file.name)
                if file_exists_in_active_jobs_or_tasks(engine, input_file_name):
                    st.error(f"A job or task for this .set file is already running or pending. Please wait until it completes or fails.")
                else:
                    if st.button("Confirm and Upload"):
                        save_path = os.path.join(config.WATCH_FOLDER, uploaded_file.name)
                        with open(save_path, "wb") as f:
                            f.write(raw_bytes)
                        meta_data = {
                            "user_id": int(user_id),
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "ea_name": ea_name,
                            "original_filename": uploaded_file.name
                        }
                        meta_path = save_path + ".meta.json"
                        try:
                            with open(meta_path, "w", encoding="utf-8") as f:
                                json.dump(meta_data, f)
                            st.success(f"File {uploaded_file.name} uploaded and queued for job creation.")
                            st.info(
                                "Controller will process the file and create the job automatically using your user ID and extracted metadata.")
                        except Exception as e:
                            st.error(f"Failed to save meta file: {e}")
    except Exception as e:
        st.error(f"Failed to process upload: {e}")

st.markdown("---")

st.header("All Jobs (Master Table)")
with st.expander("Filters"):
    current_user = st.session_state.get("username", "Me")
    user_options = ["Any", current_user]
    selected_user = st.selectbox("Filter by User", user_options, key="user_filter")
    selected_user_value = None if selected_user == "Any" else selected_user

    status_options = [
        ("Any", None),
        ("New", JOB_STATUS_NEW),
        ("Queued", JOB_STATUS_QUEUED),
        ("In Progress", JOB_STATUS_IN_PROGRESS),
        ("Completed Success", JOB_STATUS_COMPLETED_SUCCESS),
        ("Completed Partial", JOB_STATUS_COMPLETED_PARTIAL),
        ("Failed", JOB_STATUS_FAILED),
    ]
    status_labels = [label for label, val in status_options]
    status_values = [val for label, val in status_options]
    selected_status_idx = st.selectbox("Filter by Job Status", range(len(status_options)), format_func=lambda i: status_labels[i], key="status_filter")
    selected_status_value = status_values[selected_status_idx]
    filter_btn = st.button("Apply Filter")

jobs_df = load_jobs(
    user_name=selected_user_value,
    status=selected_status_value,
)

if jobs_df.empty:
    st.info("No jobs found.")
else:
    jobs_df_display = jobs_df.copy().reset_index(drop=True)
    ss = st.session_state
    if 'selected_job_index' not in ss:
        ss.selected_job_index = None
    if 'jobs_df_display' not in ss or not jobs_df_display.drop(columns=['selected'], errors='ignore').equals(
            ss.jobs_df_display.drop(columns=['selected'], errors='ignore') if 'selected' in ss.jobs_df_display.columns else ss.jobs_df_display):
        ss.jobs_df_display = jobs_df_display.copy()
        ss.jobs_df_display['selected'] = [False] * len(jobs_df_display)
        ss.selected_job_index = None

    cols = ss.jobs_df_display.columns.tolist()
    if 'selected' in cols:
        cols.insert(0, cols.pop(cols.index('selected')))
        ss.jobs_df_display = ss.jobs_df_display[cols]

    def select_change():
        edited_rows = ss.job_table['edited_rows']
        if edited_rows:
            recent_idx = list(edited_rows)[-1]
            was_checked = edited_rows[recent_idx].get("selected", False)
            ss.jobs_df_display['selected'] = False
            if was_checked:
                ss.jobs_df_display.at[recent_idx, "selected"] = True
                ss.selected_job_index = recent_idx
            else:
                ss.selected_job_index = None

    # Dynamically determine column width for "ea_name" (optional)
    if not ss.jobs_df_display.empty and "ea_name" in ss.jobs_df_display.columns:
        max_ea_len = ss.jobs_df_display["ea_name"].map(str).map(len).max()
    else:
        max_ea_len = 20
    ea_col_width = min(max(200, max_ea_len * 9), 600)

    st.markdown("#### Job List (Single Select)")
    with st.container(border=True):
        st.data_editor(
            ss.jobs_df_display,
            hide_index=True,
            key='job_table',
            on_change=select_change,
            width='stretch',  # UI ENHANCEMENT: new Streamlit API
            column_config={
                "selected": st.column_config.CheckboxColumn("Select", required=False),
                "ea_name": st.column_config.Column(width=ea_col_width),
            },
        )

    if ss.selected_job_index is not None:
        selected_job_row = ss.jobs_df_display.iloc[ss.selected_job_index]
        job_id = selected_job_row['id']
        st.markdown("#### Strategy Details for Selected Job")
        detail_df = load_details(int(job_id))
        if detail_df.empty:
            st.info("No strategy details found for this job.")
        else:
            detail_ss = st.session_state
            if 'selected_metric_index' not in detail_ss:
                detail_ss.selected_metric_index = None
            if 'detail_df_display' not in detail_ss or not detail_df.equals(detail_ss.detail_df_display.drop(columns=['selected'], errors='ignore') if 'selected' in detail_ss.detail_df_display.columns else detail_ss.detail_df_display):
                detail_ss.detail_df_display = detail_df.copy()
                detail_ss.detail_df_display['selected'] = [False] * len(detail_df)

            cols = detail_ss.detail_df_display.columns.tolist()
            if 'selected' in cols:
                cols.insert(0, cols.pop(cols.index('selected')))
                detail_ss.detail_df_display = detail_ss.detail_df_display[cols]

            def select_metric_change():
                edited_rows = detail_ss.strategy_table['edited_rows']
                if edited_rows:
                    recent_idx = list(edited_rows)[-1]
                    was_checked = edited_rows[recent_idx].get("selected", False)
                    detail_ss.detail_df_display['selected'] = False
                    if was_checked:
                        detail_ss.detail_df_display.at[recent_idx, "selected"] = True
                        detail_ss.selected_metric_index = recent_idx
                    else:
                        detail_ss.selected_metric_index = None

            # Dynamically determine column width for set_file_name
            if not detail_ss.detail_df_display.empty and "set_file_name" in detail_ss.detail_df_display.columns:
                max_setfile_len = detail_ss.detail_df_display["set_file_name"].map(str).map(len).max()
            else:
                max_setfile_len = 20
            setfile_col_width = min(max(200, max_setfile_len * 9), 600)

            st.data_editor(
                detail_ss.detail_df_display,
                hide_index=True,
                key='strategy_table',
                on_change=select_metric_change,
                width='stretch',
                column_config={
                    "selected": st.column_config.CheckboxColumn("Select", required=False),
                    "set_file_name": st.column_config.Column(width=setfile_col_width),
                }
            )
            can_reoptimize = selected_job_row['status'] in ALLOWED_REOPTIMIZE_STATUSES

            if detail_ss.selected_metric_index is not None:
                selected_metric_row = detail_ss.detail_df_display.iloc[detail_ss.selected_metric_index]
                metric_id = selected_metric_row['metric_id']
                session_user_id = (
                    st.session_state.get("user_id")
                    or config.USER_ID
                )
                if st.button(
                    "Re-optimize selected strategy",
                    disabled=not can_reoptimize
                ):
                    # Save explicit arguments as a dictionary for clarity/maintainability
                    st.session_state['reopt_args'] = {
                        "metric_id": metric_id,
                        "job_row": selected_job_row,
                        "metric_row": selected_metric_row,
                        "user_id": session_user_id
                    }
                    st.session_state['is_reoptimizing'] = True
                    st.rerun()
            elif not can_reoptimize:
                st.info("Re-optimization only allowed for jobs with status: completed_success, completed_partial, or failed.")
    else:
        st.info("Select a job above to view strategy details.")

st.caption("This dashboard allows you to manage, upload, and analyze jobs and their strategies. For admin or advanced controls, contact support.")

# --- END OF FILE ---