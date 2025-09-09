import os
import sys
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from db.db_models import (
    Base, ControllerJob, ControllerTask, ControllerAttempt, ControllerAISuggestion,
    OptimizationSection, OptimizationParameter, ControllerArtifact, ControllerTaskLog,
    TestMetric, SetFile, Portfolio, PositionSizingResult, TradeRecord,
    User, AuditLog  # <-- Ensure these are in db_models.py
)
from db.status_constants import (
    JOB_STATUS_NEW, JOB_STATUS_QUEUED, JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_COMPLETED_SUCCESS, JOB_STATUS_COMPLETED_PARTIAL, JOB_STATUS_FAILED,
    STATUS_NEW, STATUS_QUEUED, STATUS_WORKER_IN_PROGRESS, STATUS_WORKER_COMPLETED,
    STATUS_WORKER_FAILED, STATUS_RETRYING, STATUS_FINE_TUNING, STATUS_COMPLETED_SUCCESS,
    STATUS_COMPLETED_PARTIAL, STATUS_FAILED,
)
from config import SQLALCHEMY_DATABASE_URL, SYMBOL_CSV_PATH

# Import the actual set file field extractor
from config import MT4_OPTIMIZER_PATH
if MT4_OPTIMIZER_PATH and MT4_OPTIMIZER_PATH not in sys.path:
    sys.path.append(MT4_OPTIMIZER_PATH)
import extract_setfilename_fields

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SYMBOL_LIST = extract_setfilename_fields.load_symbol_list(SYMBOL_CSV_PATH)

def get_db():
    return SessionLocal()

def extract_setfile_metadata(setfile_path):
    fields = extract_setfilename_fields.extract_fields(setfile_path, SYMBOL_LIST)
    return {
        "ea_name": fields.get("EA", ""),
        "symbol": fields.get("Symbol", ""),
        "timeframe": fields.get("Timeframe", ""),
        # Optionally add more fields...
    }

# --- Existing job/task helpers unchanged ---

def insert_job_and_task(session, meta, set_file_path, user_id="system"):
    existing_job = session.query(ControllerJob).filter_by(
        original_file=set_file_path
    ).first()
    if existing_job:
        existing_task = session.query(ControllerTask).filter_by(
            job_id=existing_job.id,
            file_path=set_file_path
        ).first()
        return existing_job.id, existing_task.id if existing_task else None, False

    job = ControllerJob(
        user_id=user_id,
        job_type="optimization",
        symbol=meta["symbol"],
        timeframe=meta["timeframe"],
        ea_name=meta["ea_name"],
        original_file=set_file_path,
        status=STATUS_NEW,
        max_attempts=1,
        attempt_count=0,
    )
    session.add(job)
    session.commit()
    task = ControllerTask(
        job_id=job.id,
        step_number=1,
        step_name="optimize",
        status=STATUS_NEW,
        assigned_worker=None,
        file_path=set_file_path,
        description=f"Optimization for {meta['ea_name']}",
        attempt_count=0,
        max_attempts=1,
    )
    session.add(task)
    session.commit()
    return job.id, task.id, True

def job_has_success(session, job_id):
    return session.query(ControllerTask).filter(
        ControllerTask.job_id == job_id,
        ControllerTask.status == STATUS_COMPLETED_SUCCESS
    ).count() > 0

def update_job_status(session, job_id):
    job = session.query(ControllerJob).filter(ControllerJob.id == job_id).first()
    if not job:
        return
    tasks = session.query(ControllerTask).filter(ControllerTask.job_id == job_id).all()
    if not tasks:
        return
    statuses = set([t.status for t in tasks])
    in_progress_statuses = {
        STATUS_NEW, STATUS_QUEUED, STATUS_WORKER_IN_PROGRESS,
        STATUS_RETRYING, STATUS_FINE_TUNING
    }
    if statuses & in_progress_statuses:
        new_status = JOB_STATUS_IN_PROGRESS
    else:
        all_success = all(t.status == STATUS_COMPLETED_SUCCESS for t in tasks)
        any_success = any(t.status == STATUS_COMPLETED_SUCCESS for t in tasks)
        any_partial = any(t.status == STATUS_COMPLETED_PARTIAL for t in tasks)
        any_failed = any(t.status == STATUS_FAILED for t in tasks)
        if all_success:
            new_status = JOB_STATUS_COMPLETED_SUCCESS
        elif any_success:
            new_status = JOB_STATUS_COMPLETED_PARTIAL
        elif any_partial or any_failed:
            new_status = JOB_STATUS_FAILED
        else:
            new_status = JOB_STATUS_FAILED
    if job.status != new_status:
        job.status = new_status
        session.commit()

def update_task_status(session, task_id, status, assigned_worker=None):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).first()
    if task:
        task.status = status
        if assigned_worker is not None:
            task.assigned_worker = assigned_worker
        task.updated_at = datetime.utcnow()
        session.commit()

def update_task_worker_job(session, task_id, worker_job_id):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).first()
    if task:
        task.worker_job_id = worker_job_id
        session.commit()

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
    session.commit()
    return attempt.id

def finish_attempt(session, attempt_id, status, error_message=None, result_json=None):
    attempt = session.query(ControllerAttempt).filter(ControllerAttempt.id == attempt_id).first()
    if attempt:
        attempt.status = status
        attempt.finished_at = datetime.utcnow()
        attempt.error_message = error_message
        attempt.result_json = result_json
        session.commit()

def update_task_heartbeat(session, task_id):
    task = session.query(ControllerTask).filter(ControllerTask.id == task_id).first()
    if task:
        task.last_heartbeat = datetime.utcnow()
        session.commit()

def get_stuck_tasks(session, threshold_minutes=60):
    cutoff = datetime.utcnow() - timedelta(minutes=threshold_minutes)
    return session.query(ControllerTask).filter(
        ControllerTask.status == "in_progress",
        ControllerTask.updated_at < cutoff
    ).all()

def requeue_task(session, task):
    task.status = "failed"
    session.commit()
    new_task = ControllerTask(
        job_id=task.job_id,
        step_number=task.step_number,
        step_name=task.step_name,
        status="queued",
        assigned_worker=None,
        file_path=task.file_path,
        description=task.description,
        attempt_count=0,
        max_attempts=task.max_attempts,
    )
    session.add(new_task)
    session.commit()

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
    session.commit()

# --- User Management & AuditLog helpers (SQLAlchemy ORM style) ---

def fetch_user_by_username(session, username):
    return session.query(User).filter_by(username=username).first()

def fetch_user_by_id(session, user_id):
    return session.query(User).filter_by(id=user_id).first()

def set_open_router_api_key(db_session, username, api_key):
    user = db_session.query(User).filter_by(username=username).first()
    if user:
        user.open_router_api_key = api_key
        db_session.commit()
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
    session.commit()
    return user.id

def update_user_status(session, user_id, status, approved_by=None):
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return
    user.status = status
    if status == 'Approved':
        user.date_approved = datetime.utcnow()
        user.approved_by = approved_by
    session.commit()

def change_user_role(session, user_id, new_role, admin_id):
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.role = new_role
        session.commit()
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
    session.commit()

def get_audit_log(session, user_id=None, limit=100):
    query = session.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return query.limit(limit).all()