from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Float, LargeBinary, BLOB, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

import bcrypt

class User:
    def __init__(self, id, username, email, password_hash, role, status, date_registered, date_approved, approved_by, profile_data):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.status = status
        self.date_registered = date_registered
        self.date_approved = date_approved
        self.approved_by = approved_by
        self.profile_data = profile_data

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

class AuditLog(Base):
    __tablename__ = 'audit_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    action = Column(String(128), nullable=False)
    target_id = Column(String(128))
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON)  # Or Text if your MySQL lacks JSON support

    # Optionally, add relationship to User
    user = relationship("User")

class ControllerJob(Base):
    __tablename__ = 'controller_jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255))
    job_type = Column(String(255))
    symbol = Column(String(255))
    timeframe = Column(String(255))
    ea_name = Column(String(255))
    original_file = Column(String(255))
    status = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    max_attempts = Column(Integer)
    attempt_count = Column(Integer)
    trace_json = Column(Text)

    tasks = relationship("ControllerTask", back_populates="job")
    ai_suggestions = relationship("ControllerAISuggestion", back_populates="job")
    set_files = relationship("SetFile", back_populates="job")
    sizing_results = relationship("PositionSizingResult", back_populates="job")
    trade_records = relationship("TradeRecord", back_populates="job")


class ControllerTask(Base):
    __tablename__ = 'controller_tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('controller_jobs.id'))
    parent_task_id = Column(Integer, ForeignKey('controller_tasks.id'), nullable=True)  # NEW: fine-tune/retry lineage
    step_number = Column(Integer)
    step_name = Column(String(255))
    status = Column(String(32))
    status_reason = Column(Text, nullable=True)              # NEW: Reason for current status
    priority = Column(Float, default=0)                      # NEW: Task priority (for queueing)
    best_so_far = Column(Integer, default=0)                 # NEW: Boolean flag (0/1) for best-so-far
    assigned_worker = Column(String(255))
    file_path = Column(Text)
    file_blob = Column(BLOB, nullable=True)  # For MySQL, use BLOB
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_heartbeat = Column(DateTime, nullable=True)
    attempt_count = Column(Integer)
    max_attempts = Column(Integer)
    fine_tune_depth = Column(Integer, default=0)             # NEW: Fine-tune chain depth (for stopping)
    last_error = Column(Text, nullable=True)                 # NEW: Last error message if any
    worker_job_id = Column(Integer)

    job = relationship("ControllerJob", back_populates="tasks")
    attempts = relationship("ControllerAttempt", back_populates="task")
    ai_suggestions = relationship("ControllerAISuggestion", back_populates="task")
    artifacts = relationship("ControllerArtifact", back_populates="task")
    logs = relationship("ControllerTaskLog", back_populates="task")
    test_metrics = relationship("TestMetric", back_populates="task")
    trade_records = relationship("TradeRecord", back_populates="task")
    parent_task = relationship("ControllerTask", remote_side=[id])  # Self-referential for lineage


class ControllerAttempt(Base):
    __tablename__ = 'controller_attempts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    attempt_number = Column(Integer)
    status = Column(String(32))
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    error_message = Column(Text)
    result_json = Column(Text)

    task = relationship("ControllerTask", back_populates="attempts")


class ControllerAISuggestion(Base):
    __tablename__ = 'controller_ai_suggestions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('controller_jobs.id'))
    task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    prompt = Column(Text)
    response = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ControllerJob", back_populates="ai_suggestions")
    task = relationship("ControllerTask", back_populates="ai_suggestions")
    sections = relationship("OptimizationSection", back_populates="suggestion")
    parameters = relationship("OptimizationParameter", back_populates="suggestion")


class OptimizationSection(Base):
    __tablename__ = 'optimization_section'
    id = Column(Integer, primary_key=True, autoincrement=True)
    suggestion_id = Column(Integer, ForeignKey('controller_ai_suggestions.id'))
    section_name = Column(String(255))
    explanation = Column(Text)

    suggestion = relationship("ControllerAISuggestion", back_populates="sections")


class OptimizationParameter(Base):
    __tablename__ = 'optimization_parameter'
    id = Column(Integer, primary_key=True, autoincrement=True)
    suggestion_id = Column(Integer, ForeignKey('controller_ai_suggestions.id'))
    parameter_name = Column(String(255))
    start = Column(Float)
    end = Column(Float)
    step = Column(Float)
    reason = Column(Text)

    suggestion = relationship("ControllerAISuggestion", back_populates="parameters")


class ControllerArtifact(Base):
    __tablename__ = 'controller_artifacts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    artifact_type = Column(String(64))
    file_name = Column(String(255))
    file_path = Column(Text)
    file_blob = Column(LargeBinary)
    link_type = Column(String(64))
    link_id = Column(Integer)
    meta_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("ControllerTask", back_populates="artifacts")


class ControllerTaskLog(Base):
    __tablename__ = 'controller_task_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    event_type = Column(String(64))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("ControllerTask", back_populates="logs")


class TestMetric(Base):
    __tablename__ = 'test_metrics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    controller_task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    metric_type = Column(String(255))
    net_profit = Column(Float)
    gross_profit = Column(Float)
    gross_loss = Column(Float)
    profit_factor = Column(Float)
    expected_payoff = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_pct = Column(Float)
    max_relative_drawdown = Column(Float)
    max_relative_drawdown_pct = Column(Float)
    absolute_drawdown = Column(Float)
    initial_deposit = Column(Float)
    total_trades = Column(Integer)
    profit_trades_pct = Column(Float)
    loss_trades_pct = Column(Float)
    largest_profit = Column(Float)
    largest_loss = Column(Float)
    recovery_factor = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    net_profit_per_initial_deposit = Column(Float)
    absolute_drawdown_per_initial_deposit = Column(Float)
    symbol = Column(String(255))
    period = Column(String(255))
    model = Column(String(255))
    bars_in_test = Column(Integer)
    ticks_modelled = Column(Integer)
    modelling_quality = Column(Float)
    mismatched_charts_errors = Column(Integer)
    spread = Column(Float)
    short_positions = Column(Integer)
    short_positions_won_pct = Column(Float)
    long_positions = Column(Integer)
    long_positions_won_pct = Column(Float)
    largest_profit_trade = Column(Float)
    largest_loss_trade = Column(Float)
    max_consecutive_wins = Column(Integer)
    max_consecutive_wins_profit = Column(Float)
    max_consecutive_profit = Column(Float)
    max_consecutive_profit_count = Column(Integer)
    max_consecutive_losses = Column(Integer)
    max_consecutive_losses_loss = Column(Float)
    max_consecutive_loss = Column(Float)
    max_consecutive_loss_count = Column(Integer)
    win_rate = Column(Float)
    metrics_json = Column(Text)
    parameters_json = Column(Text)
    summary_csv = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    min_total_recovery = Column(Float)
    min_trades = Column(Integer)
    min_max_drawdown = Column(Float)
    criteria_passed = Column(Integer)
    criteria_reason = Column(Text)
    set_file_name = Column(String(255))
    magic_number = Column(Integer)
    input_html_file = Column(Text)
    input_set_file = Column(Text)
    optimization_pass_id = Column(Integer)

    task = relationship("ControllerTask", back_populates="test_metrics")


class SetFile(Base):
    __tablename__ = 'set_files'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('controller_jobs.id'))
    file_name = Column(String(255))
    file_path = Column(Text)
    file_blob = Column(LargeBinary)
    uploaded_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    meta_json = Column(Text)

    job = relationship("ControllerJob", back_populates="set_files")


class Portfolio(Base):
    __tablename__ = 'portfolios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_name = Column(String(255))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    meta_json = Column(Text)

    sizing_results = relationship("PositionSizingResult", back_populates="portfolio")
    trade_records = relationship("TradeRecord", back_populates="portfolio")


class PositionSizingResult(Base):
    __tablename__ = 'position_sizing_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('controller_jobs.id'))
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
    method = Column(String(64))
    input_params_json = Column(Text)
    result_summary_json = Column(Text)
    simulation_blob = Column(LargeBinary)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ControllerJob", back_populates="sizing_results")
    portfolio = relationship("Portfolio", back_populates="sizing_results")


class TradeRecord(Base):
    __tablename__ = 'trade_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    controller_task_id = Column(Integer, ForeignKey('controller_tasks.id'))
    job_id = Column(Integer, ForeignKey('controller_jobs.id'))
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
    order_id = Column(Integer)
    parent_order_id = Column(Integer)
    symbol = Column(String(255))
    open_time = Column(DateTime)
    open_type = Column(String(64))
    open_price = Column(Float)
    open_size = Column(Float)
    open_sl = Column(Float)
    open_tp = Column(Float)
    close_time = Column(DateTime)
    close_type = Column(String(64))
    close_price = Column(Float)
    close_size = Column(Float)
    close_sl = Column(Float)
    close_tp = Column(Float)
    profit = Column(Float)
    balance_after_trade = Column(Float)
    commission = Column(Float)
    swap = Column(Float)
    magic_number = Column(Integer)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("ControllerTask", back_populates="trade_records")
    job = relationship("ControllerJob", back_populates="trade_records")
    portfolio = relationship("Portfolio", back_populates="trade_records")