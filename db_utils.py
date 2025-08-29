import os
import sys
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from db.db_models import *
from config import SQLALCHEMY_DATABASE_URL, SYMBOL_CSV_PATH

# Import the actual set file field extractor
from config import MT4_OPTIMIZER_PATH
import sys
if MT4_OPTIMIZER_PATH and MT4_OPTIMIZER_PATH not in sys.path:
    sys.path.append(MT4_OPTIMIZER_PATH)
import extract_setfilename_fields  # now this will work

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Load symbol list once per process
SYMBOL_LIST = extract_setfilename_fields.load_symbol_list(SYMBOL_CSV_PATH)

def get_db():
    return SessionLocal()

def extract_setfile_metadata(setfile_path):
    """
    Uses extract_setfilename_fields to extract metadata from .set filename.
    Returns a dict with keys: ea_name, symbol, timeframe, etc.
    """
    fields = extract_setfilename_fields.extract_fields(setfile_path, SYMBOL_LIST)
    # Map fields to old keys for compatibility
    return {
        "ea_name": fields.get("EA", ""),
        "symbol": fields.get("Symbol", ""),
        "timeframe": fields.get("Timeframe", ""),
        # Optionally add more fields...
        # "start_date": fields.get("StartDate", ""),
        # etc.
    }

def insert_job_and_task(session, meta, set_file_path, user_id="system"):
    job = ControllerJob(
        user_id=user_id,
        job_type="optimization",
        symbol=meta["symbol"],
        timeframe=meta["timeframe"],
        ea_name=meta["ea_name"],
        original_file=set_file_path,
        status="queued",
        max_attempts=1,
        attempt_count=0,
    )
    session.add(job)
    session.commit()
    task = ControllerTask(
        job_id=job.id,
        step_number=1,
        step_name="optimize",
        status="queued",
        assigned_worker=None,
        file_path=set_file_path,
        description=f"Optimization for {meta['ea_name']}",
        attempt_count=0,
        max_attempts=1,
    )
    session.add(task)
    session.commit()
    return job.id, task.id

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

def create_attempt(session, task_id, status="in_progress"):
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
    """
    Insert an artifact record into controller_artifacts.
    """
    # Example: using SQLAlchemy ORM
    artifact = ControllerArtifact(
        task_id=task_id,
        artifact_type=artifact_type,
        file_name=file_name,
        file_path=file_path,
        file_blob=file_blob,  # This is new!
        link_type=link_type,
        link_id=link_id,
        meta_json=meta_json
    )
    session.add(artifact)
    session.commit()