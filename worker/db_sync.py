import sqlite3
import pymysql
import os

from sqlalchemy.orm import sessionmaker

from config import (
    AGENT_DB_PATH,
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
)
from sqlalchemy import create_engine, text
from contextlib import contextmanager

# Utility: SQLAlchemy session context for controller DB
@contextmanager
def controller_db_session():
    engine = create_engine(
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT or 3306}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()

def link_artifacts_to_test_metrics_for_task(session, controller_task_id):
    """
    For a specific controller_task_id, link controller_artifacts of type 'output_set'
    to their corresponding test_metrics (by exact file_name match), but only update
    if the link_id is missing or incorrect.
    """
    # Step 1: Find all candidate artifact/test_metrics pairs that should be linked
    select_sql = text("""
        SELECT a.id AS artifact_id, t.id AS test_metrics_id, a.link_id
        FROM controller_artifacts a
        JOIN test_metrics t
          ON t.controller_task_id = a.task_id
          AND a.artifact_type = 'output_set'
          AND a.file_name = t.set_file_name
          AND a.file_blob IS NOT NULL
        WHERE a.task_id = :controller_task_id
    """)
    results = session.execute(select_sql, {'controller_task_id': controller_task_id}).fetchall()

    # Step 2: Update only if link_id is missing or incorrect
    update_sql = text("""
        UPDATE controller_artifacts
        SET link_type = 'test_metrics', link_id = :test_metrics_id
        WHERE link_id = :link_id
    """)
    count = 0
    for artifact_id, test_metrics_id, link_id in results:
        if link_id != test_metrics_id:
            session.execute(update_sql, {
                'test_metrics_id': test_metrics_id,
				'link_id': link_id
            })
            count += 1
    print(f"Linked {count} artifacts to test_metrics for controller_task_id={controller_task_id}")

def sync_test_metrics(worker_job_id):
    """
    Sync test_metrics rows for a specific worker job from agent (SQLite) to controller (MySQL) db.
    Args:
        worker_job_id (int): The job.id (out_worker_JobId) to sync.
    """
    agent_sql = """
    SELECT 
        job.controller_task_id,
        tm.metric_type,
        tm.net_profit,
        tm.gross_profit,
        tm.gross_loss,
        tm.profit_factor,
        tm.expected_payoff,
        tm.max_drawdown,
        tm.max_drawdown_pct,
        tm.max_relative_drawdown,
        tm.max_relative_drawdown_pct,
        tm.absolute_drawdown,
        tm.initial_deposit,
        tm.total_trades,
        tm.profit_trades_pct,
        tm.loss_trades_pct,
        tm.largest_profit,
        tm.largest_loss,
        tm.recovery_factor,
        tm.sharpe_ratio,
        tm.sortino_ratio,
        tm.net_profit_per_initial_deposit,
        tm.absolute_drawdown_per_initial_deposit,
        tm.symbol,
        tm.period,
        tm.model,
        tm.bars_in_test,
        tm.ticks_modelled,
        tm.modelling_quality,
        tm.mismatched_charts_errors,
        tm.spread,
        tm.short_positions,
        tm.short_positions_won_pct,
        tm.long_positions,
        tm.long_positions_won_pct,
        tm.largest_profit_trade,
        tm.largest_loss_trade,
        tm.max_consecutive_wins,
        tm.max_consecutive_wins_profit,
        tm.max_consecutive_profit,
        tm.max_consecutive_profit_count,
        tm.max_consecutive_losses,
        tm.max_consecutive_losses_loss,
        tm.max_consecutive_loss,
        tm.max_consecutive_loss_count,
        tm.win_rate,
        tm.metrics_json,
        tm.parameters_json,
        tm.summary_csv,
        tm.created_at,
        tm.start_date,
        tm.end_date,
        tm.min_total_recovery,
        tm.min_trades,
        tm.min_max_drawdown,
        tm.criteria_passed,
        tm.criteria_reason,
        tm.set_file_name,
        tm.magic_number,
        tm.input_html_file,
        tm.input_set_file,
        tm.optimization_pass_id
    FROM set_file_jobs job
    JOIN set_file_steps steps ON steps.job_id = job.id
    JOIN test_metrics tm ON tm.step_id = steps.id
    WHERE job.id = ?
    """

    # Connect to agent (SQLite)
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (worker_job_id,))
    rows = agent_cursor.fetchall()

    insert_sql = """
    INSERT INTO test_metrics (
        controller_task_id,
        metric_type,
        net_profit,
        gross_profit,
        gross_loss,
        profit_factor,
        expected_payoff,
        max_drawdown,
        max_drawdown_pct,
        max_relative_drawdown,
        max_relative_drawdown_pct,
        absolute_drawdown,
        initial_deposit,
        total_trades,
        profit_trades_pct,
        loss_trades_pct,
        largest_profit,
        largest_loss,
        recovery_factor,
        sharpe_ratio,
        sortino_ratio,
        net_profit_per_initial_deposit,
        absolute_drawdown_per_initial_deposit,
        symbol,
        period,
        model,
        bars_in_test,
        ticks_modelled,
        modelling_quality,
        mismatched_charts_errors,
        spread,
        short_positions,
        short_positions_won_pct,
        long_positions,
        long_positions_won_pct,
        largest_profit_trade,
        largest_loss_trade,
        max_consecutive_wins,
        max_consecutive_wins_profit,
        max_consecutive_profit,
        max_consecutive_profit_count,
        max_consecutive_losses,
        max_consecutive_losses_loss,
        max_consecutive_loss,
        max_consecutive_loss_count,
        win_rate,
        metrics_json,
        parameters_json,
        summary_csv,
        created_at,
        start_date,
        end_date,
        min_total_recovery,
        min_trades,
        min_max_drawdown,
        criteria_passed,
        criteria_reason,
        set_file_name,
        magic_number,
        input_html_file,
        input_set_file,
        optimization_pass_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Connect to controller (MySQL)
    ctrl_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT or 3306,
        charset='utf8mb4',
        autocommit=False
    )
    ctrl_cursor = ctrl_conn.cursor()

    try:
        for row in rows:
            ctrl_cursor.execute(insert_sql, row)
        ctrl_conn.commit()
        print(f"Copied {len(rows)} test_metrics rows from agent job {worker_job_id} to controller DB.")
    except Exception as e:
        ctrl_conn.rollback()
        print(f"Error during sync: {e}")
    finally:
        agent_cursor.close()
        agent_conn.close()
        ctrl_cursor.close()
        ctrl_conn.close()

def sync_trade_records(worker_job_id):
    """
    Sync trade_records rows for a specific worker job from agent (SQLite) to controller (MySQL) db.
    Args:
        worker_job_id (int): The job.id (out_worker_JobId) to sync.
    """
    agent_sql = """
    SELECT
        o.controller_task_id,
        o.order_id,
        o.symbol,
        o.open_time,
        o.open_type,
        o.open_price,
        o.open_size,
        o.open_sl,
        o.open_tp,
        c.close_time,
        c.close_type,
        c.close_price,
        c.close_size,
        c.close_sl,
        c.close_tp,
        c.profit,
        c.balance_after_trade,
        o.magic_number,
        o.comment
    FROM (
        SELECT
            j.controller_task_id,
            s.job_id,
            t.step_id,
            t.order_id,
            t.symbol,
            t.time AS open_time,
            t.type AS open_type,
            t.price AS open_price,
            t.size AS open_size,
            t.sl AS open_sl,
            t.tp AS open_tp,
            t.magic_number,
            t.comment
        FROM
            trades t
        JOIN set_file_steps s ON t.step_id = s.id
        JOIN set_file_jobs j ON s.job_id = j.id
        WHERE t.type IN ('buy', 'sell')
          AND j.id = ?
    ) o
    JOIN (
        SELECT
            j.controller_task_id,
            s.job_id,
            t.step_id,
            t.order_id,
            t.time AS close_time,
            t.type AS close_type,
            t.price AS close_price,
            t.size AS close_size,
            t.sl AS close_sl,
            t.tp AS close_tp,
            t.profit,
            t.balance AS balance_after_trade
        FROM
            trades t
        JOIN set_file_steps s ON t.step_id = s.id
        JOIN set_file_jobs j ON s.job_id = j.id
        WHERE t.type LIKE 'close%'
          AND j.id = ?
    ) c
    ON o.job_id = c.job_id
       AND o.step_id = c.step_id
       AND o.order_id = c.order_id
       AND o.open_time < c.close_time
    """

    insert_sql = """
    INSERT INTO trade_records (
        controller_task_id,
        order_id,
        symbol,
        open_time,
        open_type,
        open_price,
        open_size,
        open_sl,
        open_tp,
        close_time,
        close_type,
        close_price,
        close_size,
        close_sl,
        close_tp,
        profit,
        balance_after_trade,
        magic_number,
        comment
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Connect to agent (SQLite)
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (worker_job_id, worker_job_id))
    rows = agent_cursor.fetchall()

    # Connect to controller (MySQL)
    ctrl_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT or 3306,
        charset='utf8mb4',
        autocommit=False
    )
    ctrl_cursor = ctrl_conn.cursor()

    try:
        for row in rows:
            ctrl_cursor.execute(insert_sql, row)
        ctrl_conn.commit()
        print(f"Copied {len(rows)} trade_records rows from agent job {worker_job_id} to controller DB.")
    except Exception as e:
        ctrl_conn.rollback()
        print(f"Error during sync: {e}")
    finally:
        agent_cursor.close()
        agent_conn.close()
        ctrl_cursor.close()
        ctrl_conn.close()

def sync_artifacts(worker_job_id):
    """
    Sync set_file_artifacts rows for a specific worker job from agent (SQLite) to controller (MySQL) db,
    then link artifacts to test_metrics for this job's controller_task_id.
    Args:
        worker_job_id (int): The job.id (out_worker_JobId) to sync.
    """
    agent_sql = """
    SELECT
        job.controller_task_id,
        art.artifact_type,
        art.file_path,
        art.meta_json,
        art.file_blob,
        art.link_type,
        art.link_id
    FROM set_file_jobs job
    JOIN set_file_steps steps ON steps.job_id = job.id
    JOIN set_file_artifacts art ON art.step_id = steps.id
    WHERE job.id = ?
    """

    insert_sql = """
    INSERT INTO controller_artifacts (
        task_id,
        artifact_type,
        file_path,
        file_name,
        meta_json,
        file_blob,
        link_type,
        link_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Connect to agent (SQLite)
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (worker_job_id,))
    rows = agent_cursor.fetchall()

    # Get controller_task_id (assume all rows for this worker_job_id share the same controller_task_id)
    controller_task_id = rows[0][0] if rows else None

    # Connect to controller (MySQL)
    ctrl_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT or 3306,
        charset='utf8mb4',
        autocommit=False
    )
    ctrl_cursor = ctrl_conn.cursor()

    try:
        for row in rows:
            (
                controller_task_id,
                artifact_type,
                file_path,
                meta_json,
                file_blob,
                link_type,
                link_id,
            ) = row
            file_name = os.path.basename(file_path) if file_path else None
            ctrl_cursor.execute(
                insert_sql,
                (
                    controller_task_id,
                    artifact_type,
                    file_path,
                    file_name,
                    meta_json,
                    file_blob,
                    link_type,
                    link_id,
                )
            )
        ctrl_conn.commit()
        print(f"Copied {len(rows)} artifact rows from agent job {worker_job_id} to controller DB.")

        # --- Linking step ---
        if controller_task_id:
            with controller_db_session() as session:
                link_artifacts_to_test_metrics_for_task(session, controller_task_id)
            print(f"Linked artifacts to test_metrics for controller_task_id={controller_task_id}")

    except Exception as e:
        ctrl_conn.rollback()
        print(f"Error during artifact sync: {e}")
    finally:
        agent_cursor.close()
        agent_conn.close()
        ctrl_cursor.close()
        ctrl_conn.close()

def sync_ai_suggestions(worker_job_id):
    """
    Sync optimization_suggestion, optimization_section, and optimization_parameter from agent (SQLite)
    to controller (MySQL) for a specific worker job, using correct controller job/task ids.
    """
    import sqlite3
    import pymysql

    # 1. Fetch suggestions (parent)
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    agent_cursor = agent_conn.cursor()
    # Use controller_job_id and controller_task_id for the insert mapping!
    agent_cursor.execute(
        """
        SELECT
            sug.id,
            j.controller_job_id AS job_id,      -- controller_jobs.id for controller DB
            j.controller_task_id AS task_id,    -- controller_tasks.id for controller DB
            sug.mode,                           -- used as prompt (since agent does not store prompt/response)
            sug.created_at
        FROM set_file_jobs j
        JOIN set_file_steps s ON s.job_id = j.id
        JOIN optimization_suggestion sug ON sug.step_id = s.id
        WHERE j.id = ?
        """, (worker_job_id,)
    )
    suggestion_rows_raw = agent_cursor.fetchall()
    # Prepare for controller_ai_suggestions insert (id, job_id, task_id, prompt, response, created_at)
    suggestion_rows = [
        (
            row[0],  # id
            row[1],  # job_id (controller_job_id)
            row[2],  # task_id (controller_task_id)
            row[3] if row[3] is not None else "",  # prompt (use mode from agent)
            "",     # response (not in agent db)
            row[4]  # created_at
        )
        for row in suggestion_rows_raw
    ]

    # 2. Fetch sections (children)
    suggestion_ids = [row[0] for row in suggestion_rows_raw]
    section_rows = []
    if suggestion_ids:
        ph = ",".join("?" for _ in suggestion_ids)
        agent_cursor.execute(
            f"""
            SELECT
                sec.id,
                sec.suggestion_id,
                sec.section_name,
                sec.explanation
            FROM optimization_section sec
            WHERE sec.suggestion_id IN ({ph})
            """,
            suggestion_ids
        )
        section_rows = agent_cursor.fetchall()

    # 3. Fetch parameters (children)
    parameter_rows = []
    if suggestion_ids:
        ph = ",".join("?" for _ in suggestion_ids)
        agent_cursor.execute(
            f"""
            SELECT
                param.id,
                param.suggestion_id,
                param.parameter_name,
                param.start,
                param.end,
                param.step,
                param.reason
            FROM optimization_parameter param
            WHERE param.suggestion_id IN ({ph})
            """,
            suggestion_ids
        )
        parameter_rows = agent_cursor.fetchall()

    # Connect to controller (MySQL)
    ctrl_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT or 3306,
        charset='utf8mb4',
        autocommit=False
    )
    ctrl_cursor = ctrl_conn.cursor()

    try:
        # 1. Insert controller_ai_suggestions
        insert_suggestion_sql = """
        INSERT INTO controller_ai_suggestions (
            id,
            job_id,
            task_id,
            prompt,
            response,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            job_id=VALUES(job_id),
            task_id=VALUES(task_id),
            prompt=VALUES(prompt),
            response=VALUES(response),
            created_at=VALUES(created_at)
        """
        for row in suggestion_rows:
            ctrl_cursor.execute(insert_suggestion_sql, row)

        # 2. Insert optimization_section
        insert_section_sql = """
        INSERT INTO optimization_section (
            id,
            suggestion_id,
            section_name,
            explanation
        ) VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            suggestion_id=VALUES(suggestion_id),
            section_name=VALUES(section_name),
            explanation=VALUES(explanation)
        """
        for row in section_rows:
            ctrl_cursor.execute(insert_section_sql, row)

        # 3. Insert optimization_parameter
        insert_parameter_sql = """
        INSERT INTO optimization_parameter (
            id,
            suggestion_id,
            parameter_name,
            start,
            end,
            step,
            reason
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            suggestion_id=VALUES(suggestion_id),
            parameter_name=VALUES(parameter_name),
            start=VALUES(start),
            end=VALUES(end),
            step=VALUES(step),
            reason=VALUES(reason)
        """
        for row in parameter_rows:
            ctrl_cursor.execute(insert_parameter_sql, row)

        ctrl_conn.commit()
        print(f"Copied {len(suggestion_rows)} suggestions, {len(section_rows)} sections, {len(parameter_rows)} parameters from agent job {worker_job_id} to controller DB.")
    except Exception as e:
        ctrl_conn.rollback()
        print(f"Error during AI suggestions sync: {e}")
    finally:
        agent_cursor.close()
        agent_conn.close()
        ctrl_cursor.close()
        ctrl_conn.close()