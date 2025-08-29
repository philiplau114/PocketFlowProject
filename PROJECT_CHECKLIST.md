# Trading Optimization Platform – Project Checklist and Integration Test Plan

---

## 1. **Environment & Dependencies**

- [ ] Finalize and secure `.env` with all real credentials, file paths, tokens.
- [ ] Install all required Python packages (`sqlalchemy`, `mysql-connector-python`, `redis`, `python-dotenv`, etc.).
- [ ] Ensure UiPath CLI or workflow runner is installed and accessible for workers.

---

## 2. **Database**

- [ ] Deploy the provided MySQL schema to your server.
- [ ] Run `db_models.py` to verify ORM mappings work.
- [ ] If needed, set up Alembic (or equivalent) for DB migrations.
- [ ] Test DB connection from all service containers/scripts.

---

## 3. **Core Service Scripts**

### Controller
- [ ] Test that `controller/main.py` detects new `.set` files and inserts correct records in `controller_jobs` and `controller_tasks`.
- [ ] Ensure new tasks are pushed to the Redis queue.

### Worker
- [ ] Test that `worker/main.py` pulls tasks from Redis, updates task status, and logs results in `controller_attempts`.
- [ ] Ensure worker can run the optimization process (e.g., via UiPath CLI or your actual workflow engine).
- [ ] Ensure attempt and task status is updated on both success and failure.

### Supervisor
- [ ] Test that `supervisor/supervisor.py` detects stuck or long-running tasks and re-queues as needed.
- [ ] Verify detection of inactive workers and alerting.

### Shared
- [ ] Ensure all DB access is via SQLAlchemy models and proper session handling.
- [ ] Ensure logging and error handling is consistent across all scripts.

---

## 4. **Notifications**

- [ ] Test `notify.py` email configuration (send a test email).
- [ ] Test Telegram configuration (send a test message).
- [ ] Ensure notifications are triggered for:
  - [ ] New jobs (if desired)
  - [ ] Worker failures
  - [ ] Stuck jobs/tasks
  - [ ] Inactive workers

---

## 5. **Deployment**

- [ ] Write/update Dockerfiles for controller, worker, supervisor if using containers.
- [ ] Prepare Docker Compose or Kubernetes manifests as needed.
- [ ] Verify environment variable passing and volume mounts for input/output folders.

---

## 6. **Logging & Monitoring**

- [ ] Verify all scripts write logs to the appropriate directory (`LOG_DIR`).
- [ ] Set up log rotation or external log aggregation if necessary.
- [ ] Optionally, implement a dashboard or basic web UI for job/task status.

---

## 7. **Integration Tests**

### End-to-End Workflow

- [ ] Place a new `.set` file in the watch folder.  
  **Expected:**  
  - Controller creates a `controller_jobs` and `controller_tasks` record.
  - Task is pushed to Redis.

- [ ] Worker picks up the task.  
  **Expected:**  
  - Task status set to `in_progress`, `assigned_worker` is set.
  - A new `controller_attempts` record is created.

- [ ] Worker runs optimization process.  
  **On success:**  
  - Task status set to `completed`.
  - Attempt status set to `completed`, `result_json` populated.

  **On failure:**  
  - Task status set to `failed`.
  - Attempt status set to `failed`, `error_message` populated.

- [ ] Supervisor detects stuck/inactive tasks (simulate by killing worker or pausing process).  
  **Expected:**  
  - Supervisor marks old task as `failed` and creates a new queued task.

### Notification Triggers

- [ ] Simulate a worker failure or long-running task and verify email/Telegram alerts are sent.
- [ ] Simulate a stuck task and verify notification and re-queuing.

---

## 8. **Documentation**

- [ ] Write clear README for setup, running, and troubleshooting.
- [ ] Document `.env` variables and example values.
- [ ] Document expected workflow for users and operators.
- [ ] Optionally, add API or CLI usage documentation.

---

## 9. **Production Readiness**

- [ ] Ensure secrets are never committed to source control.
- [ ] Secure database and Redis access.
- [ ] Review and test backup/disaster recovery for DB and artifacts.
- [ ] Monitor resource usage and scale workers as needed.

---

## 10. **Future/Advanced Tasks**

- [ ] Build a web UI for job/task/worker monitoring and user submissions.
- [ ] Add multi-user authentication and permissions if needed.
- [ ] Add automated result validation and reporting.
- [ ] Implement historical analytics and usage metrics.

---

## Notes

- **Update this checklist** as you discover additional requirements or edge cases during implementation and testing.
- **Keep integration tests semi-automated** (e.g., via pytest or a shell script) for regression testing after changes.

---