# Fine-Tune Logic in Controller - Comprehensive Explanation

## Overview

The PocketFlow Project implements an intelligent fine-tuning system in the controller that automatically creates optimized trading strategy tasks based on the performance of previous executions. This document explains the complete fine-tune logic workflow.

## Core Components

### 1. Main Controller Loop (`controller/main.py`)

The controller runs a continuous loop that:
- Processes new .set files from a watch folder
- Handles post-worker status updates  
- Manages task queueing with priority-based scheduling
- Triggers fine-tuning when conditions are met

### 2. Fine-Tune Task Creation (`controller/controller_utils.py`)

The `spawn_fine_tune_task()` function creates new fine-tuned tasks based on the best-performing results from parent tasks.

## Fine-Tune Workflow

### Step 1: Task Completion Analysis

When a worker completes a task (`STATUS_WORKER_COMPLETED`), the controller:

1. **Retrieves Performance Metrics**:
   ```python
   task_ids = [task.id]
   metrics_map = get_task_metric_scores(session, task_ids)
   m = metrics_map.get(task.id, {})
   task._distance = m.get('distance')  # normalized_total_distance_to_good
   task._score = m.get('score')        # weighted_score
   ```

2. **Evaluates Success Criteria**:
   - **Full Success**: `distance <= DISTANCE_THRESHOLD (0.1)` AND `score >= SCORE_THRESHOLD (0.8)`
   - **Partial Success**: `distance <= DISTANCE_THRESHOLD (0.1)` OR `score >= SCORE_THRESHOLD (0.8)`
   - **Failure**: Neither threshold met

### Step 2: Fine-Tune Decision Logic

```python
if (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) and \
   (task._score is not None and task._score >= SCORE_THRESHOLD):
    # Full success - mark as completed
    mark_task_success(session, task)
elif (task._distance is not None and task._distance <= DISTANCE_THRESHOLD) or \
     (task._score is not None and task._score >= SCORE_THRESHOLD):
    # Partial success - create fine-tune task if within depth limit
    mark_task_partial(session, task)
    if (task.fine_tune_depth or 0) < MAX_FINE_TUNE_DEPTH:
        child = spawn_fine_tune_task(session, task)
        queue_task_to_redis(r, child)
else:
    # Failure - retry or fail permanently
    if (task.attempt_count or 0) < (task.max_attempts or TASK_MAX_ATTEMPTS):
        mark_task_retrying(session, task)
    else:
        mark_task_failed(session, task, reason="Max attempts reached")
```

### Step 3: Fine-Tune Task Creation Process

The `spawn_fine_tune_task()` function performs these steps:

1. **Find Best Performance Metrics**:
   ```sql
   SELECT tm.id
   FROM test_metrics tm
   WHERE tm.controller_task_id = :task_id
   ORDER BY tm.normalized_total_distance_to_good ASC, tm.weighted_score DESC
   LIMIT 1
   ```

2. **Locate Corresponding Artifact**:
   ```python
   artifact = session.query(ControllerArtifact).filter(
       ControllerArtifact.artifact_type == 'output_set',
       ControllerArtifact.link_type == 'test_metrics',
       ControllerArtifact.link_id == best_metric_id
   ).order_by(ControllerArtifact.id.desc()).first()
   ```

3. **Create Child Task**:
   ```python
   child = ControllerTask(
       job_id=parent_task.job_id,
       parent_task_id=parent_task.id,
       step_number=(parent_task.step_number or 0) + 1,
       step_name="fine_tune",
       status=STATUS_FINE_TUNING,
       status_reason="Spawned for fine-tuning",
       priority=parent_task.priority,
       file_path=artifact.file_path,      # Use best artifact's path
       file_blob=artifact.file_blob,      # Use best artifact's data
       fine_tune_depth=(parent_task.fine_tune_depth or 0) + 1,
       # ... other fields
   )
   ```

## Configuration Parameters

### Fine-Tune Limits
- **MAX_FINE_TUNE_DEPTH**: Maximum depth of fine-tuning (default: 2)
- **TASK_MAX_ATTEMPTS**: Maximum retry attempts per task (default: 3)

### Performance Thresholds
- **DISTANCE_THRESHOLD**: Maximum acceptable distance to good performance (default: 0.1)
- **SCORE_THRESHOLD**: Minimum acceptable weighted score (default: 0.8)

### Priority System
- **AGING_FACTOR**: How much task age affects priority (default: 1.0)

## Priority System for Fine-Tune Tasks

The `hybrid_priority()` function assigns priorities:

```python
def hybrid_priority(task, now=None):
    now = now or datetime.utcnow()
    base = task.priority or 10
    age_minutes = ((now - (task.updated_at or task.created_at)).total_seconds() / 60)
    aging = AGING_FACTOR * age_minutes
    
    if getattr(task, "status", None) == STATUS_RETRYING:
        return (base * (2 ** (task.attempt_count or 1))) + aging
    elif getattr(task, "step_name", None) == "fine_tune" and task._distance is not None:
        return (1000 - int(task._distance * 100)) + aging  # Higher priority for better distance
    else:
        return base + aging
```

**Fine-tune tasks get special priority**: `1000 - (distance * 100)`, meaning better-performing tasks get higher priority.

## Task Status Flow

```
New Task (STATUS_NEW)
    ↓
Queued (STATUS_QUEUED)
    ↓
Worker Processing (STATUS_WORKER_IN_PROGRESS)
    ↓
Worker Completed (STATUS_WORKER_COMPLETED)
    ↓
Performance Evaluation:
    ├── Full Success → STATUS_COMPLETED_SUCCESS
    ├── Partial Success → STATUS_COMPLETED_PARTIAL
    │   └── Create Fine-Tune Task (STATUS_FINE_TUNING)
    └── Failure → STATUS_RETRYING or STATUS_FAILED
```

## Key Insights

1. **Quality-Based Fine-Tuning**: Only partially successful tasks trigger fine-tuning, ensuring resources focus on promising strategies.

2. **Best Result Selection**: Fine-tune tasks use the best-performing artifact from the parent task, not just the latest.

3. **Depth Limiting**: The `MAX_FINE_TUNE_DEPTH` prevents infinite fine-tuning loops.

4. **Intelligent Prioritization**: Fine-tune tasks with better distance scores get higher execution priority.

5. **Artifact Inheritance**: Child tasks inherit the optimized parameters and data from the best-performing parent execution.

## Error Handling

- If no test metrics exist for a parent task, fine-tuning fails with an exception
- If no corresponding artifact exists for the best metric, fine-tuning fails with an exception
- Tasks that exceed maximum attempts or fine-tune depth are marked as failed

This fine-tuning system creates an evolutionary optimization approach where successful trading strategies are iteratively refined to achieve better performance metrics.