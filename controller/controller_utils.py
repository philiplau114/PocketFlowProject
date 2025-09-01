from sqlalchemy import text
from db.db_models import ControllerTask, ControllerArtifact
from datetime import datetime

def get_task_metric_scores(session, task_ids):
    if not task_ids:
        return {}
    sql = text(f"""
        SELECT controller_task_id, 
               normalized_total_distance_to_good AS distance, 
               weighted_score AS score
        FROM v_test_metrics_scored
        WHERE controller_task_id IN :task_ids
        ORDER BY id DESC
    """)
    result = session.execute(sql, {"task_ids": tuple(task_ids)})
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
    Creates a new ControllerTask as a fine-tune child of parent_task.
    Selects the best test_metrics (lowest distance, highest score) and corresponding output_set artifact.
    Sets the new task's file_blob to the best artifact's file_blob.
    Commits and returns new task and the file_blob (optional).
    """
    from db.db_models import ControllerTask, TestMetrics, ControllerArtifact
    from sqlalchemy import and_
    from datetime import datetime

    # 1. Find the "best" test_metrics for this parent task (lowest distance, highest score)
    best_metric = session.execute(
        """
        SELECT tm.id
        FROM test_metrics tm
        WHERE tm.controller_task_id = :task_id
        ORDER BY tm.normalized_total_distance_to_good ASC, tm.weighted_score DESC
        LIMIT 1
        """, {"task_id": parent_task.id}
    ).fetchone()

    if not best_metric:
        raise Exception(f"No test_metrics found for parent_task_id={parent_task.id}")

    best_metric_id = best_metric[0]

    # 2. Find the corresponding output_set artifact
    artifact = session.query(ControllerArtifact).filter(
        ControllerArtifact.artifact_type == 'output_set',
        ControllerArtifact.link_type == 'test_metrics',
        ControllerArtifact.link_id == best_metric_id
    ).order_by(ControllerArtifact.id.desc()).first()

    if not artifact:
        raise Exception(f"No controller_artifacts of type 'output_set' linked to test_metrics id={best_metric_id}")

    # 3. Create new ControllerTask (child), file_blob is set from artifact
    child = ControllerTask(
        job_id=parent_task.job_id,
        parent_task_id=parent_task.id,
        step_number=(parent_task.step_number or 0) + 1,
        step_name="fine_tune",
        status="fine_tuning",
        status_reason="Spawned for fine-tuning",
        priority=parent_task.priority,
        best_so_far=0,
        file_path=artifact.file_path,  # <-- Set to artifact's file_path!
        description=parent_task.description,
        attempt_count=0,
        max_attempts=parent_task.max_attempts,
        fine_tune_depth=(parent_task.fine_tune_depth or 0) + 1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        file_blob=artifact.file_blob,
    )
    session.add(child)
    session.commit()

    return child

def queue_task_to_redis(r, task):
    """
    Queue the task to Redis, always using file_blob from the ControllerTask itself.
    """
    import json
    import os
    from config import REDIS_QUEUE
    file_blob_key = f"task:{task.id}:input_blob"
    if task.file_blob:
        r.set(file_blob_key, task.file_blob)
    task_data = {
        "job_id": task.job_id,
        "task_id": task.id,
        'set_file_name': os.path.basename(task.file_path),
        "input_blob_key": file_blob_key,
        "ea_name": getattr(task, "ea_name", None),
        "symbol": getattr(task, "symbol", None),
        "timeframe": getattr(task, "timeframe", None),
    }
    r.lpush(REDIS_QUEUE, json.dumps(task_data))