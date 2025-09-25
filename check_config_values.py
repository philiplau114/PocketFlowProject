import config

def check_config_variable(name):
    value = getattr(config, name, None)
    print(f"{name}: {'FOUND' if value is not None else 'MISSING/None'} | Value: {value}")

config_vars = [
    "SQLALCHEMY_DATABASE_URL",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "AGENT_DB_PATH",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_MAIN_QUEUE",
    "REDIS_PROCESSING_QUEUE",
    "REDIS_DEAD_LETTER_QUEUE",
    "REDIS_QUEUE",
    "SET_FILE_LIBRARY",
    "WATCH_FOLDER",
    "PROCESSED_FOLDER",
    "SYMBOL_CSV_PATH",
    "MT4_OPTIMIZER_PATH",
    "USER_ID",
    "WORKER_ID",
    "UIPATH_CLI",
    "UIPATH_WORKFLOW",
    "OUTPUT_JSON_DIR",
    "OUTPUT_JSON_POLL_INTERVAL",
    "OUTPUT_JSON_WARNING_MODULUS",
    "UIPATH_MT4_LIB",
    "UIPATH_CONFIG",
    "UIPATH_JOB_MAX_SECONDS",
    "UIPATH_KILL_FILE",
    "LOG_DIR",
    "TASK_MAX_ATTEMPTS",
    "MAX_FINE_TUNE_DEPTH",
    "DISTANCE_THRESHOLD",
    "SCORE_THRESHOLD",
    "AGING_FACTOR",
    "JOB_STUCK_THRESHOLD_MINUTES",
    "WORKER_INACTIVE_THRESHOLD_MINUTES",
    "SUPERVISOR_POLL_INTERVAL",
    "SMTP_SERVER",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "EMAIL_TO",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "RELOAD_INTERVAL",
    "LOCK_RETRY_COUNT",
    "LOCK_RETRY_SLEEP"
]

print("==== Checking config.py loaded variables ====")
for var in config_vars:
    check_config_variable(var)
print("==== Done ====")