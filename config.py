import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Paths to env files
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
ENV_CONTROLLER_PATH = os.path.join(PROJECT_ROOT, 'controller', '.env.controller')
ENV_WORKER_PATH = os.path.join(PROJECT_ROOT, 'worker', '.env.worker')

load_dotenv(ENV_PATH, override=False)
load_dotenv(ENV_CONTROLLER_PATH, override=True)
load_dotenv(ENV_WORKER_PATH, override=True)

# Database
SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306)) if os.getenv('MYSQL_PORT') else None
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

AGENT_DB_PATH = os.getenv('AGENT_DB_PATH')

# Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_QUEUE = os.getenv('REDIS_QUEUE', 'pfai_tasks')

# Watch folder for input .set files
SET_FILE_LIBRARY = os.getenv('SET_FILE_LIBRARY')
WATCH_FOLDER = os.path.join(SET_FILE_LIBRARY, '01_user_inputs') if SET_FILE_LIBRARY else None
# 99_processed folder for moved/processed .set files
PROCESSED_FOLDER = os.path.join(SET_FILE_LIBRARY, '99_processed') if SET_FILE_LIBRARY else None


# Symbol list for .set file parsing
SYMBOL_CSV_PATH = os.getenv('SYMBOL_CSV_PATH', os.path.join(SET_FILE_LIBRARY or '', 'SymbolList.csv'))
MT4_OPTIMIZER_PATH = os.getenv('MT4_OPTIMIZER_PATH')

# Worker/Controller/User
USER_ID = os.getenv('USER_ID', 'system')
WORKER_ID = os.getenv('WORKER_ID', 'worker_1')

# UiPath or workflow runner (for worker)
UIPATH_CLI = os.getenv('UIPATH_CLI')
UIPATH_WORKFLOW = os.getenv('UIPATH_WORKFLOW')

# Worker-specific output and polling settings
OUTPUT_JSON_DIR = os.getenv('OUTPUT_JSON_DIR')
OUTPUT_JSON_POLL_INTERVAL = int(os.getenv('OUTPUT_JSON_POLL_INTERVAL', 5))
OUTPUT_JSON_WARNING_MODULUS = int(os.getenv('OUTPUT_JSON_WARNING_MODULUS', 150))

UIPATH_MT4_LIB= os.getenv('UIPATH_MT4_LIB')
UIPATH_CONFIG= os.getenv('UIPATH_CONFIG')

# UiPath job management (worker)
UIPATH_JOB_MAX_SECONDS = int(os.getenv('UIPATH_JOB_MAX_SECONDS', 43200))
UIPATH_KILL_FILE = os.getenv('UIPATH_KILL_FILE')

# Logging
LOG_DIR = os.getenv('LOG_DIR', 'logs')

# Controller Retry and optimization/fairness thresholds
TASK_MAX_ATTEMPTS = int(os.getenv('MAX_ATTEMPTS', 3))
MAX_FINE_TUNE_DEPTH = int(os.getenv('MAX_FINE_TUNE_DEPTH', 2))
DISTANCE_THRESHOLD = float(os.getenv('DISTANCE_THRESHOLD', 0.1))
SCORE_THRESHOLD = float(os.getenv('SCORE_THRESHOLD', 0.8))
AGING_FACTOR = float(os.getenv('AGING_FACTOR', 1.0))

# Supervisor polling intervals and thresholds (in minutes)
JOB_STUCK_THRESHOLD_MINUTES = int(os.getenv('JOB_STUCK_THRESHOLD_MINUTES', 60))
WORKER_INACTIVE_THRESHOLD_MINUTES = int(os.getenv('WORKER_INACTIVE_THRESHOLD_MINUTES', 5))
SUPERVISOR_POLL_INTERVAL = int(os.getenv('SUPERVISOR_POLL_INTERVAL', 60))

# Email notification
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')

# Telegram notification
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')