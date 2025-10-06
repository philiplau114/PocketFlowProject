import os
import hashlib
from datetime import datetime
import json
import sqlalchemy

def log_reoptimize_history(engine, job_id, metric_id, trigger_type, user_id, status_at_trigger, output_set_file, meta=None):
    import logging
    sql = """
        INSERT INTO reoptimize_history
        (job_id, metric_id, triggered_at, trigger_type, user_id, status_at_trigger, output_set_file, meta)
        VALUES (:job_id, :metric_id, :triggered_at, :trigger_type, :user_id, :status_at_trigger, :output_set_file, :meta)
    """
    try:
        with engine.begin() as conn:  # this context manager will commit or rollback automatically
            conn.execute(
                sqlalchemy.text(sql),
                {
                    'job_id': int(job_id),
                    'metric_id': int(metric_id),
                    'triggered_at': datetime.utcnow(),
                    'trigger_type': trigger_type,  # "manual" or "auto"
                    'user_id': int(user_id),
                    'status_at_trigger': status_at_trigger,
                    'output_set_file': output_set_file,
                    'meta': json.dumps(meta) if meta else None
                }
            )
    except Exception as e:
        logging.error(f"[log_reoptimize_history] Failed to log reoptimize history: {e}")
        raise
def get_output_set_artifact(engine, metric_id):
    sql = """
    SELECT a.file_blob, a.file_name, j.status
    FROM controller_artifacts a, controller_tasks t, controller_jobs j 
    WHERE a.task_id = t.id
      AND j.id = t.job_id
      AND a.link_type = 'test_metrics'
      AND a.artifact_type = 'output_set'
      AND a.link_id = :link_id
    ORDER BY a.created_at DESC
    LIMIT 1
    """
    with engine.connect() as conn:
        res = conn.execute(sqlalchemy.text(sql), {"link_id": int(metric_id)})
        row = res.fetchone()
        if not row:
            raise Exception(f"No output_set artifact found for metric_id {metric_id}")
        return row[0], row[1], row[2]  # file_blob, file_name, job_status

def generate_short_suffix(metric_id):
    # Uses the last 4 hex chars of a hash of metric_id and timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_str = f"{metric_id}_{timestamp}"
    hash_str = hashlib.sha1(unique_str.encode()).hexdigest()[:4]
    return hash_str

def reoptimize_by_metric(engine, metric_id, job_row, metric_row, user_id, *, meta_extras=None, prefix="R", watch_folder=None):
    # Get artifact and job status for this metric
    file_blob, file_name, job_status = get_output_set_artifact(engine, metric_id)
    base = os.path.splitext(file_name)[0]
    suffix = generate_short_suffix(metric_id)
    new_file_name = f"{base}_{prefix}{suffix}.set"
    save_path = os.path.join(watch_folder, new_file_name)
    with open(save_path, "wb") as f:
        f.write(file_blob)

    # Build meta data
    meta_data = {
        "user_id": int(user_id),
        "symbol": str(job_row['symbol']),
        "timeframe": str(job_row.get('timeframe') or job_row.get('period')),
        "ea_name": str(job_row.get('ea_name')),
        "original_filename": new_file_name,
        "reoptimize_source_metric_id": int(metric_id),
        "reoptimize_source_job_id": int(job_row['id'])
    }
    if meta_extras:
        meta_data.update(meta_extras)
    meta_path = save_path + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_data, f)

    # Determine trigger_type from prefix
    trigger_type = "auto" if prefix == "A" else "manual"

    # status_at_trigger is the job_status we just fetched
    status_at_trigger = job_status

    # Log to reoptimize_history
    log_reoptimize_history(
        engine=engine,
        job_id=job_row['id'],
        metric_id=metric_id,
        trigger_type=trigger_type,
        user_id=user_id,
        status_at_trigger=status_at_trigger,
        output_set_file=new_file_name,
        meta=meta_data
    )

    return save_path