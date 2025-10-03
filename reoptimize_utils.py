import os
import hashlib
from datetime import datetime
import json
import sqlalchemy

def get_output_set_artifact(engine, metric_id):
    sql = """
    SELECT file_blob, file_name
    FROM controller_artifacts
    WHERE link_type = 'test_metrics'
      AND artifact_type = 'output_set'
      AND link_id = :link_id
    ORDER BY created_at DESC
    LIMIT 1
    """
    with engine.connect() as conn:
        res = conn.execute(sqlalchemy.text(sql), {"link_id": int(metric_id)})
        row = res.fetchone()
        if not row:
            raise Exception(f"No output_set artifact found for metric_id {metric_id}")
        return row[0], row[1]

def generate_short_suffix(metric_id):
    # Uses the last 4 hex chars of a hash of metric_id and timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_str = f"{metric_id}_{timestamp}"
    hash_str = hashlib.sha1(unique_str.encode()).hexdigest()[:4]
    return hash_str

def reoptimize_by_metric(engine, metric_id, job_row, metric_row, user_id, *, meta_extras=None, prefix="R", watch_folder=None):
    # Get artifact
    file_blob, file_name = get_output_set_artifact(engine, metric_id)
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
    return save_path