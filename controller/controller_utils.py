from sqlalchemy import text
from db.db_models import ControllerTask, ControllerArtifact
from datetime import datetime

from sqlalchemy import text

from sqlalchemy import text
from db.status_constants import STATUS_FINE_TUNING

def get_task_metric_scores(session, task_ids):
    if not task_ids:
        return {}
    # Build named placeholders
    placeholders = ', '.join([f':id{i}' for i in range(len(task_ids))])
    sql = text(f"""
        SELECT controller_task_id, 
               normalized_total_distance_to_good AS distance, 
               weighted_score AS score
        FROM v_test_metrics_scored
        WHERE controller_task_id IN ({placeholders})
        ORDER BY id DESC
    """)
    params = {f'id{i}': v for i, v in enumerate(task_ids)}
    result = session.execute(sql, params)
    scores = {}
    for row in result:
        if row.controller_task_id not in scores:
            scores[row.controller_task_id] = {
                "distance": row.distance,
                "score": row.score,
            }
    return scores

def spawn_fine_tune_task(session, parent_task):
    """
    Spawns a fine-tune child task for the given parent task.
    Uses the best test metric (lowest distance, highest score) from v_test_metrics_scored view.
    Commits and returns new task and the file_blob (optional).
    """
    from db.db_models import ControllerTask, ControllerArtifact
    from sqlalchemy import and_, text
    from datetime import datetime

    # 1. Find the "best" test_metrics for this parent task (lowest distance, highest score)
    best_metric = session.execute(
        text("""
            SELECT tm.id
            FROM v_test_metrics_scored tm
            WHERE tm.controller_task_id = :task_id
            ORDER BY tm.normalized_total_distance_to_good ASC, tm.weighted_score DESC
            LIMIT 1
        """), {"task_id": parent_task.id}
    ).fetchone()

    if not best_metric:
        raise RuntimeError(f"No test_metrics found for task {parent_task.id}")

    best_metric_id = best_metric.id

    # 2. Prepare fine-tune child task fields
    fine_tune_task = ControllerTask(
        job_id=parent_task.job_id,
        parent_task_id=parent_task.id,
        step_number=(parent_task.step_number or 1) + 1,
        step_name="fine_tune",
        status="new",
        best_so_far=0,
        priority=parent_task.priority,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        fine_tune_depth=(parent_task.fine_tune_depth or 0) + 1,
        file_path=parent_task.file_path,
        description=f"Fine-tune for parent task {parent_task.id}",
        attempt_count=0,
        max_attempts=parent_task.max_attempts,
        # You may wish to add more fields as needed
    )
    # Optionally copy file_blob or other relevant fields if needed
    fine_tune_task.file_blob = parent_task.file_blob

    session.add(fine_tune_task)
    session.commit()
    return fine_tune_task

def queue_task_to_redis(r, task):
    """
    Queue the task to Redis, always using file_blob from the ControllerTask itself.
    """
    import json
    import os
    from config import REDIS_QUEUE
    print(
        f"DEBUG: queue_task_to_redis called with task.id={task.id} ({type(task.id)}), task.job_id={task.job_id} ({type(task.job_id)})")
    file_blob_key = f"task:{task.id}:input_blob"
    if task.file_blob:
        r.set(file_blob_key, task.file_blob)
    task_data = {
        "job_id": task.job_id,
        "task_id": task.id,
        'set_file_name': os.path.basename(task.file_path),
        "input_blob_key": file_blob_key,
        # Fetch from the job relationship!
        "ea_name": getattr(task.job, "ea_name", None),
        "symbol": getattr(task.job, "symbol", None),
        "timeframe": getattr(task.job, "timeframe", None),
    }
    print(f"DEBUG: task_data = {task_data}")
    r.lpush(REDIS_QUEUE, json.dumps(task_data))