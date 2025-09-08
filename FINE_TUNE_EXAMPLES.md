# Fine-Tune Logic Examples

## Example 1: Successful Fine-Tuning Scenario

### Initial Task
- **Task ID**: 1001
- **Job ID**: 500
- **File**: `EURUSD_Strategy_v1.set`
- **Fine-tune depth**: 0 (original task)

### After Worker Completion
```
Performance Metrics:
- Distance: 0.15 (above threshold of 0.1)
- Score: 0.85 (above threshold of 0.8)
- Result: Partial Success (score meets threshold)
```

### Fine-Tune Task Creation
```sql
-- Step 1: Find best metrics
SELECT tm.id FROM test_metrics tm 
WHERE tm.controller_task_id = 1001
ORDER BY tm.normalized_total_distance_to_good ASC, tm.weighted_score DESC
LIMIT 1
-- Returns: metric_id = 2001

-- Step 2: Find artifact
SELECT * FROM controller_artifacts 
WHERE artifact_type = 'output_set' 
  AND link_type = 'test_metrics' 
  AND link_id = 2001
-- Returns: artifact with optimized parameters
```

### Child Task Created
```
Task ID: 1002
Job ID: 500
Parent Task ID: 1001
Step Name: "fine_tune"
Status: "fine_tuning"
Fine-tune Depth: 1
File Blob: [optimized parameters from best artifact]
Priority: 1000 - (15) + aging = 985 + aging
```

## Example 2: Priority Comparison

### Task Queue Scenario
```
Tasks waiting to be processed:

1. Regular new task:
   - Priority: 10 + aging = 10 + (5 × 1.0) = 15

2. Retrying task (2nd attempt):
   - Priority: (10 × 2²) + aging = 40 + 5 = 45

3. Fine-tune task (distance = 0.08):
   - Priority: (1000 - 8) + aging = 992 + 5 = 997

Queue order: Fine-tune (997) > Retry (45) > New (15)
```

## Example 3: Fine-Tune Depth Limiting

### Scenario: Deep Fine-Tuning Chain
```
Original Task (depth=0) → distance=0.12, score=0.75
├─ Partial success, creates fine-tune task

Fine-tune Task 1 (depth=1) → distance=0.09, score=0.82  
├─ Partial success, creates fine-tune task

Fine-tune Task 2 (depth=2) → distance=0.07, score=0.85
├─ Partial success, but depth=2 = MAX_FINE_TUNE_DEPTH
└─ No further fine-tuning allowed
```

## Example 4: Failure and Retry Logic

### Scenario: Poor Performance
```
Task Performance:
- Distance: 0.25 (above threshold)
- Score: 0.60 (below threshold)
- Result: Complete failure

Action Taken:
if (attempt_count=1) < (max_attempts=3):
    status = "retrying"
    attempt_count = 2
    priority = (10 × 2²) + aging = 40 + aging
else:
    status = "failed"
```

## Example 5: Artifact Selection Logic

### Multiple Test Results for Same Task
```
Test Metrics for Task 1001:
1. distance=0.20, score=0.70 (metric_id=2001)
2. distance=0.15, score=0.75 (metric_id=2002) 
3. distance=0.10, score=0.85 (metric_id=2003) ← BEST (lowest distance)
4. distance=0.12, score=0.90 (metric_id=2004)

Selected: metric_id=2003 (distance=0.10, score=0.85)
Reason: Lowest distance takes precedence in ORDER BY clause
```

## Example 6: Real-World Configuration Impact

### Development vs Production Settings

#### Development Environment
```
DISTANCE_THRESHOLD = 0.2    # More lenient
SCORE_THRESHOLD = 0.6       # Lower bar
MAX_FINE_TUNE_DEPTH = 3     # Allow deeper tuning
```

#### Production Environment  
```
DISTANCE_THRESHOLD = 0.1    # Stricter requirements
SCORE_THRESHOLD = 0.8       # Higher quality bar
MAX_FINE_TUNE_DEPTH = 2     # Controlled depth
```

### Impact on Fine-Tuning Frequency
- **Development**: More tasks trigger fine-tuning, enabling rapid iteration
- **Production**: Only high-quality results trigger fine-tuning, ensuring resource efficiency

## Key Takeaways

1. **Evolutionary Optimization**: Each fine-tune iteration uses the best results from the previous generation
2. **Quality Gating**: Only partially successful tasks generate fine-tune children
3. **Resource Management**: Depth limits and priority system prevent resource exhaustion
4. **Intelligent Selection**: Best artifacts are selected by distance first, then score
5. **Configurable Thresholds**: Environment-specific tuning for different use cases