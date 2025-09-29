import os
import sys
import time
import logging
from sqlalchemy import create_engine, and_, text
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.exc import OperationalError
import pandas as pd
from datetime import datetime, timedelta
from db.db_models import (
    Base, ControllerJob, ControllerTask, ControllerAttempt, ControllerAISuggestion,
    OptimizationSection, OptimizationParameter, ControllerArtifact, ControllerTaskLog,
    TestMetric, SetFile, Portfolio, PortfolioSet, PositionSizingResult, TradeRecord,
    User, AuditLog
)
from db.status_constants import (
    JOB_STATUS_NEW, JOB_STATUS_QUEUED, JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_COMPLETED_SUCCESS, JOB_STATUS_COMPLETED_PARTIAL, JOB_STATUS_FAILED,
    STATUS_NEW, STATUS_QUEUED, STATUS_WORKER_IN_PROGRESS, STATUS_WORKER_COMPLETED,
    STATUS_WORKER_FAILED, STATUS_RETRYING, STATUS_FINE_TUNING, STATUS_COMPLETED_SUCCESS,
    STATUS_COMPLETED_PARTIAL, STATUS_FAILED,
)
from config import (
    SQLALCHEMY_DATABASE_URL, SYMBOL_CSV_PATH, LOCK_RETRY_COUNT, LOCK_RETRY_SLEEP
)

# Import the actual set file field extractor
from config import MT4_OPTIMIZER_PATH
if MT4_OPTIMIZER_PATH and MT4_OPTIMIZER_PATH not in sys.path:
    sys.path.append(MT4_OPTIMIZER_PATH)
import extract_setfilename_fields

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600  # Optional
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SYMBOL_LIST = extract_setfilename_fields.load_symbol_list(SYMBOL_CSV_PATH)

def get_db():
    return SessionLocal()

def safe_commit(session):
    for attempt in range(LOCK_RETRY_COUNT):
        try:
            session.commit()
            return
        except OperationalError as e:
            logging.error(f"DB commit failed (attempt {attempt+1}/{LOCK_RETRY_COUNT}): {e}")
            if "Lock wait timeout exceeded" in str(e):
                session.rollback()
                time.sleep(LOCK_RETRY_SLEEP * (attempt + 1))
            else:
                raise
    raise RuntimeError("Failed to commit after lock timeout retries.")

def extract_setfile_metadata(setfile_path):
    fields = extract_setfilename_fields.extract_fields(setfile_path, SYMBOL_LIST)
    return {
        "ea_name": fields.get("EA", ""),
        "symbol": fields.get("Symbol", ""),
        "timeframe": fields.get("Timeframe", ""),
    }

def insert_job_and_task(session, meta, set_file_path, user_id="system", allow_duplicate=False):
    """
    Insert a new job and its first task.
    - If allow_duplicate is False (default), check if a job/task with this set_file_path already exists and return if so.
    - If allow_duplicate is True, always create a new job/task, even if path matches a previous one (for re-optimize).
    - max_attempts for both job and task are set from config (not hardcoded).
    """
    from config import TASK_MAX_ATTEMPTS  # Or use MAX_ATTEMPTS if that's your config variable name

    # Only block duplicates if allow_duplicate is False (default)
    if not allow_duplicate:
        existing_job = session.query(ControllerJob).filter_by(
            original_file=set_file_path
        ).first()
        if existing_job:
            existing_task = session.query(ControllerTask).filter_by(
                job_id=existing_job.id,
                file_path=set_file_path
            ).first()
            return existing_job.id, existing_task.id if existing_task else None, False

    # Always create new job/task if allow_duplicate=True
    job = ControllerJob(
        user_id=user_id,
        job_type="optimization",
        symbol=meta.get("symbol", ""),
        timeframe=meta.get("timeframe", ""),
        ea_name=meta.get("ea_name", ""),
        original_file=set_file_path,
        status=STATUS_NEW,
        max_attempts=TASK_MAX_ATTEMPTS,
        attempt_count=0,
    )
    session.add(job)
    safe_commit(session)
    task = ControllerTask(
        job_id=job.id,
        step_number=1,
        step_name="optimize",
        status=STATUS_NEW,
        assigned_worker=None,
        file_path=set_file_path,
        description=f"Optimization for {meta.get('ea_name', '')}",
        attempt_count=0,
        max_attempts=TASK_MAX_ATTEMPTS,
    )
    session.add(task)
    safe_commit(session)
    return job.id, task.id, True

def job_has_success(session, job_id):
    return session.query(ControllerTask).filter(
        ControllerTask.job_id == job_id,
        ControllerTask.status == STATUS_COMPLETED_SUCCESS
    ).count() > 0

def update_job_status(session, job_id):
    """
    Job Status Update Design

    The update_job_status function determines the overall status of a job by examining the statuses of all its associated tasks.
    The status assignment follows these rules, in priority order:

    1. If any task is in an in-progress state (NEW, QUEUED, WORKER_IN_PROGRESS, RETRYING, or FINE_TUNING),
       the job is considered IN_PROGRESS. This ensures the job remains active while any work is ongoing.

    2. Otherwise, if any task has COMPLETED_SUCCESS status, the job is marked as COMPLETED_SUCCESS.
       This means the job is considered successful if at least one of its tasks succeeded, regardless of the outcome of other tasks.

    3. Otherwise, if all tasks have FAILED status, the job is marked as FAILED.
       This covers the scenario where every attempt for the job has been unsuccessful.

    4. Otherwise (i.e., not in-progress, not any success, not all failed), the job is marked as COMPLETED_PARTIAL.
       This typically captures cases where some tasks are partially complete (e.g., COMPLETED_PARTIAL) but none fully succeeded.

    This design prioritizes IN_PROGRESS above all, then considers any success as a job-level success, then full failure, and finally partial completion.
    It is intentionally optimistic: any success elevates the job to a successful state.

    Example Scenarios:
    - If any task is still running, the job is IN_PROGRESS.
    - If any task succeeded, the job is COMPLETED_SUCCESS (even if some failed or are partial).
    - If all tasks failed, the job is FAILED.
    - If some tasks are partial (but none succeeded and none are running), the job is COMPLETED_PARTIAL.

    This logic ensures the job status gives a clear, actionable summary at a glance.
    """
    job = session.query(ControllerJob).filter(ControllerJob.id == job_id).with_for_update().first()
    if not job:
        return
    tasks = session.query(ControllerTask).filter(ControllerTask.job_id == job_id).all()
    if not tasks:
        return

    statuses = set(t.status for t in tasks)
    in_progress_statuses = {
        STATUS_NEW, STATUS_QUEUED, STATUS_WORKER_IN_PROGRESS,
        STATUS_RETRYING, STATUS_FINE_TUNING
    }

    if statuses & in_progress_statuses:
        new_status = JOB_STATUS_IN_PROGRESS
    elif any(t.status == STATUS_COMPLETED_SUCCESS for t in tasks):
        new_status = JOB_STATUS_COMPLETED_SUCCESS
    elif all(t.status == STATUS_FAILED for t in tasks):
        new_status = JOB_STATUS_FAILED
    else:
        new_status = JOB_STATUS_COMPLETED_PARTIAL

    if job.status != new_status:
        job.status = new_status
        safe_commit(session)

def update_task_status(session, task_id, status, assigned_worker=None):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).with_for_update().first()
    if task:
        task.status = status
        if assigned_worker is not None:
            task.assigned_worker = assigned_worker
        task.updated_at = datetime.utcnow()
        safe_commit(session)

def update_task_worker_job(session, task_id, worker_job_id):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).with_for_update().first()
    if task:
        task.worker_job_id = worker_job_id
        safe_commit(session)

def create_attempt(session, task_id, status=STATUS_WORKER_IN_PROGRESS):
    last_attempt = session.query(ControllerAttempt).filter(
        ControllerAttempt.task_id == task_id
    ).order_by(ControllerAttempt.attempt_number.desc()).first()
    attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1
    attempt = ControllerAttempt(
        task_id=task_id,
        attempt_number=attempt_number,
        status=status,
        started_at=datetime.utcnow()
    )
    session.add(attempt)
    safe_commit(session)
    return attempt.id

def finish_attempt(session, attempt_id, status, error_message=None, result_json=None):
    attempt = session.query(ControllerAttempt).filter(ControllerAttempt.id == attempt_id).with_for_update().first()
    if attempt:
        attempt.status = status
        attempt.finished_at = datetime.utcnow()
        attempt.error_message = error_message
        attempt.result_json = result_json
        safe_commit(session)

def update_task_heartbeat(session, task_id):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).with_for_update().first()
    if task:
        task.last_heartbeat = datetime.utcnow()
        safe_commit(session)

def get_stuck_tasks(session, threshold_minutes=60):
    cutoff = datetime.utcnow() - timedelta(minutes=threshold_minutes)
    return session.query(ControllerTask).filter(
        ControllerTask.status == "in_progress",
        ControllerTask.updated_at < cutoff
    ).all()

def requeue_task(session, task):
    """
    Sets a stuck task's status to 'retrying' and updates its timestamp.
    Does NOT increment attempt_count.
    Only the controller should increment attempt_count when actually queuing to worker.
    """
    locked_task = session.query(ControllerTask).filter(ControllerTask.id == task.id).with_for_update().first()
    if locked_task and locked_task.status != "failed":
        locked_task.status = "retrying"
        locked_task.updated_at = datetime.utcnow()
        safe_commit(session)

def get_inactive_workers(session, threshold_minutes=5):
    cutoff = datetime.utcnow() - timedelta(minutes=threshold_minutes)
    tasks = session.query(ControllerTask).filter(
        ControllerTask.status == "in_progress",
        ControllerTask.updated_at < cutoff,
        ControllerTask.assigned_worker != None
    ).all()
    return list(set([t.assigned_worker for t in tasks if t.assigned_worker]))

def insert_artifact(session, task_id, artifact_type, file_name, file_path, file_blob=None, link_type=None, link_id=None, meta_json=None):
    artifact = ControllerArtifact(
        task_id=task_id,
        artifact_type=artifact_type,
        file_name=file_name,
        file_path=file_path,
        file_blob=file_blob,
        link_type=link_type,
        link_id=link_id,
        meta_json=meta_json
    )
    session.add(artifact)
    safe_commit(session)

def store_set_file_summary(session, metric_id, summary_md):
    artifact = session.query(ControllerArtifact).filter_by(
        artifact_type="set_file_summary",
        link_type="test_metrics",
        link_id=metric_id
    ).with_for_update().first()
    if artifact:
        artifact.file_blob = summary_md.encode("utf-8")
        artifact.file_name = f"set_file_summary_{metric_id}.md"
    else:
        artifact = ControllerArtifact(
            artifact_type="set_file_summary",
            file_name=f"set_file_summary_{metric_id}.md",
            file_blob=summary_md.encode("utf-8"),
            link_type="test_metrics",
            link_id=metric_id
        )
        session.add(artifact)
    safe_commit(session)

# --- User Management & AuditLog helpers (SQLAlchemy ORM style) ---

def fetch_user_by_username(session, username):
    return session.query(User).filter_by(username=username).first()

def fetch_user_by_id(session, user_id):
    return session.query(User).filter_by(id=user_id).first()

def set_open_router_api_key(db_session, username, api_key):
    user = db_session.query(User).filter_by(username=username).with_for_update().first()
    if user:
        user.open_router_api_key = api_key
        safe_commit(db_session)
        return True
    return False

def get_open_router_api_key(db_session, username):
    user = db_session.query(User).filter_by(username=username).first()
    return user.open_router_api_key if user else None

def create_user(session, username, email, password_hash, open_router_api_key=None):
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        status='Pending',
        date_registered=datetime.utcnow(),
        open_router_api_key=open_router_api_key
    )
    session.add(user)
    safe_commit(session)
    return user.id

def update_user_status(session, user_id, status, approved_by=None):
    user = session.query(User).filter_by(id=user_id).with_for_update().first()
    if not user:
        return
    user.status = status
    if status == 'Approved':
        user.date_approved = datetime.utcnow()
        user.approved_by = approved_by
    safe_commit(session)

def change_user_role(session, user_id, new_role, admin_id):
    user = session.query(User).filter_by(id=user_id).with_for_update().first()
    if user:
        user.role = new_role
        safe_commit(session)
        log_action(session, admin_id, "Role Changed", target_id=user_id, details={"new_role": new_role})

def log_action(session, user_id, action, target_id=None, details=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_id=target_id,
        timestamp=datetime.utcnow(),
        details=details if details else None
    )
    session.add(log)
    safe_commit(session)

def get_audit_log(session, user_id=None, limit=100):
    query = session.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return query.limit(limit).all()

# --- Portfolio Management ORM functions ---

def get_user_portfolios(session, user_id):
    return session.query(Portfolio).filter_by(user_id=user_id).all()

def create_portfolio(session, user_id, portfolio_name, description=""):
    new_portfolio = Portfolio(
        user_id=user_id,
        portfolio_name=portfolio_name,
        description=description,
        meta_json=None
    )
    session.add(new_portfolio)
    safe_commit(session)
    return new_portfolio

def get_portfolio_strategies(session, portfolio_id):
    sql = text("""
        SELECT
            v.id AS metric_id,
            v.set_file_name,
            v.symbol,
            v.net_profit,
            v.weighted_score,
            v.win_rate,
            v.normalized_total_distance_to_good
        FROM Portfolio_Sets ps
        JOIN v_test_metrics_scored v ON ps.test_metrics_id = v.id
        WHERE ps.portfolio_id = :portfolio_id
        ORDER BY v.normalized_total_distance_to_good ASC, v.weighted_score DESC
    """)
    result = session.execute(sql, {"portfolio_id": portfolio_id})
    rows = result.fetchall()
    df = pd.DataFrame(rows, columns=[
        "metric_id",
        "set_file_name",
        "symbol",
        "net_profit",
        "weighted_score",
        "win_rate",
        "normalized_total_distance_to_good"
    ])
    return df

def add_strategy_to_portfolio(session, portfolio_id, metric_id):
    ps = PortfolioSet(portfolio_id=portfolio_id, test_metrics_id=metric_id)
    session.add(ps)
    safe_commit(session)
    return True

def remove_strategy_from_portfolio(session, portfolio_id, metric_id):
    ps = session.query(PortfolioSet).filter_by(portfolio_id=portfolio_id, test_metrics_id=metric_id).with_for_update().first()
    if ps:
        session.delete(ps)
        safe_commit(session)
        return True
    return False

def load_available_strategies(session):
    sql = text("""
        SELECT
            id,
            set_file_name,
            symbol,
            net_profit,
            weighted_score,
            win_rate,
            normalized_total_distance_to_good
        FROM v_test_metrics_scored
        ORDER BY normalized_total_distance_to_good ASC, weighted_score DESC
    """)
    result = session.execute(sql)
    rows = result.fetchall()
    df = pd.DataFrame(rows, columns=[
        "metric_id",
        "set_file_name",
        "symbol",
        "net_profit",
        "weighted_score",
        "win_rate",
        "normalized_total_distance_to_good"
    ])
    return df

def get_portfolio_symbols(session, portfolio_id):
    sql = text("""
        SELECT DISTINCT v.symbol
        FROM Portfolio_Sets ps
        JOIN v_test_metrics_scored v ON ps.test_metrics_id = v.id
        WHERE ps.portfolio_id = :portfolio_id
    """)
    rows = session.execute(sql, {"portfolio_id": portfolio_id}).fetchall()
    return [row[0] for row in rows]

def extract_symbol_code(symbol):
    """Extracts the symbol code from a string like 'AUDCHF (Australian Dollar vs Swiss Franc)'."""
    return symbol.split()[0] if symbol else symbol

def get_portfolio_currency_correlation(session, portfolio_id, timeframe='H1'):
    symbols = get_portfolio_symbols(session, portfolio_id)
    # Clean symbols to just the code
    symbols = [extract_symbol_code(s) for s in symbols]
    if not symbols:
        return pd.DataFrame(columns=["symbol1", "symbol2", "correlation"])
    symbol_tuple = tuple(symbols)
    placeholders = ','.join([':s'+str(i) for i in range(len(symbol_tuple))])
    params = {f's{i}': symbol for i, symbol in enumerate(symbol_tuple)}
    params.update({'tf': timeframe})
    sql = text(f"""
        SELECT symbol1, symbol2, correlation
        FROM Correlation_Matrix
        WHERE timeframe = :tf
        AND symbol1 IN ({placeholders}) AND symbol2 IN ({placeholders})
    """)
    result = session.execute(sql, params)
    rows = result.fetchall()
    return pd.DataFrame(rows, columns=["symbol1", "symbol2", "correlation"])

def aggregate_correlation(df):
    if df.empty:
        return {'average_correlation': None, 'max_correlation': None, 'high_corr_pairs': []}
    avg_corr = df['correlation'].mean()
    max_corr = df['correlation'].max()
    # Exclude self-correlation
    high_corr_pairs = df[
        (df['correlation'] > 0.7) & (df['symbol1'] != df['symbol2'])
    ][['symbol1', 'symbol2', 'correlation']].values.tolist()

    # Deduplicate: only keep (A, B) where A < B (alphabetically)
    deduped = []
    seen = set()
    for a, b, corr in high_corr_pairs:
        key = tuple(sorted([a, b]))
        if key not in seen:
            deduped.append([key[0], key[1], corr])
            seen.add(key)
    return {
        'average_correlation': avg_corr,
        'max_correlation': max_corr,
        'high_corr_pairs': deduped
    }