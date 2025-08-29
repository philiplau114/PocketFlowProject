import sqlite3
import pymysql
import os
from config import (
    AGENT_DB_PATH,
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
)

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
    Sync set_file_artifacts rows for a specific worker job from agent (SQLite) to controller (MySQL) db.
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
    INSERT INTO set_file_artifacts (
        controller_task_id,
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
    to controller (MySQL) for a specific worker job, in the order:
    1. optimization_suggestion
    2. optimization_section
    3. optimization_parameter
    """
    # 1. Fetch suggestions (parent)
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    agent_cursor = agent_conn.cursor()
    # Fetch all suggestions for the job, along with their step id for later joins
    agent_cursor.execute(
        """
        SELECT
            sug.id,
            j.controller_task_id,
            sug.step_id,
            sug.suggestion_json,
            sug.score,
            sug.created_at
        FROM set_file_jobs j
        JOIN set_file_steps s ON s.job_id = j.id
        JOIN optimization_suggestion sug ON sug.step_id = s.id
        WHERE j.id = ?
        """, (worker_job_id,)
    )
    suggestion_rows = agent_cursor.fetchall()

    # 2. Fetch sections (children)
    # Get all suggestion IDs for this job
    suggestion_ids = [row[0] for row in suggestion_rows]
    section_rows = []
    if suggestion_ids:
        ph = ",".join("?" for _ in suggestion_ids)
        agent_cursor.execute(
            f"""
            SELECT
                sec.id,
                sec.suggestion_id,
                sec.section_name,
                sec.section_json,
                sec.created_at
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
                param.param_name,
                param.param_value,
                param.param_json,
                param.created_at
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
        # 1. Insert optimization_suggestion (controller_ai_suggestions)
        insert_suggestion_sql = """
        INSERT INTO controller_ai_suggestions (
            id,
            controller_task_id,
            step_id,
            suggestion_json,
            score,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            controller_task_id=VALUES(controller_task_id),
            step_id=VALUES(step_id),
            suggestion_json=VALUES(suggestion_json),
            score=VALUES(score),
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
            section_json,
            created_at
        ) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            suggestion_id=VALUES(suggestion_id),
            section_name=VALUES(section_name),
            section_json=VALUES(section_json),
            created_at=VALUES(created_at)
        """
        for row in section_rows:
            ctrl_cursor.execute(insert_section_sql, row)

        # 3. Insert optimization_parameter
        insert_parameter_sql = """
        INSERT INTO optimization_parameter (
            id,
            suggestion_id,
            param_name,
            param_value,
            param_json,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            suggestion_id=VALUES(suggestion_id),
            param_name=VALUES(param_name),
            param_value=VALUES(param_value),
            param_json=VALUES(param_json),
            created_at=VALUES(created_at)
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