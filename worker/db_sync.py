import sqlite3
import pymysql
import os
import base64

from sqlalchemy.orm import sessionmaker
from config import (
    AGENT_DB_PATH,
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
)
from sqlalchemy import create_engine, text
from contextlib import contextmanager

encoded_key = os.getenv("SQLCIPHER_KEY")
if not encoded_key:
    raise Exception("Environment variable SQLCIPHER_KEY is not set.")

sqlcipher_key = base64.b64decode(encoded_key).decode()

# Utility: SQLAlchemy session context for controller DB (used ONLY for linking step, not main inserts)
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

def link_artifacts_to_test_metrics_for_task(ctrl_conn, controller_task_id):
    select_sql = """
        SELECT a.id AS artifact_id, t.id AS test_metrics_id, a.link_id
        FROM controller_artifacts a
        JOIN test_metrics t
          ON t.controller_task_id = a.task_id
          AND a.artifact_type = 'output_set'
          AND a.file_name = t.set_file_name
          AND a.file_blob IS NOT NULL
        WHERE a.task_id = %s
    """
    update_sql = """
        UPDATE controller_artifacts
        SET link_type = 'test_metrics', link_id = %s
        WHERE link_id = %s
    """
    cursor = ctrl_conn.cursor()
    cursor.execute(select_sql, (controller_task_id,))
    results = cursor.fetchall()
    count = 0
    for artifact_id, test_metrics_id, link_id in results:
        if link_id != test_metrics_id:
            cursor.execute(update_sql, (test_metrics_id, link_id))
            count += 1
    print(f"[DEBUG] Linked {count} artifacts to test_metrics for controller_task_id={controller_task_id}")
    cursor.close()

def sync_trade_records(step_id, test_metrics_id, ctrl_conn):
    agent_sql = """
    SELECT
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
            t.order_id,
            t.symbol,
            t.time AS open_time,
            t.type AS open_type,
            t.price AS open_price,
            t.size AS open_size,
            t.sl AS open_sl,
            t.tp AS open_tp,
            t.magic_number,
            t.comment,
            t.step_id AS step_id
        FROM
            trades t
        WHERE t.type IN ('buy', 'sell')
          AND t.step_id = ?
    ) o
    JOIN (
        SELECT
            t.order_id,
            t.time AS close_time,
            t.type AS close_type,
            t.price AS close_price,
            t.size AS close_size,
            t.sl AS close_sl,
            t.tp AS close_tp,
            t.profit,
            t.balance AS balance_after_trade,
            t.step_id AS step_id
        FROM
            trades t
        WHERE t.type LIKE 'close%'
          AND t.step_id = ?
    ) c
    ON o.step_id = c.step_id
       AND o.order_id = c.order_id
       AND o.open_time < c.close_time
    """
    insert_sql = """
    INSERT INTO trade_records (
        test_metrics_id,
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
    trade_record_columns = [
        "order_id",
        "symbol",
        "open_time",
        "open_type",
        "open_price",
        "open_size",
        "open_sl",
        "open_tp",
        "close_time",
        "close_type",
        "close_price",
        "close_size",
        "close_sl",
        "close_tp",
        "profit",
        "balance_after_trade",
        "magic_number",
        "comment"
    ]
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    #agent_conn.execute(f"PRAGMA key = '{sqlcipher_key}';")
    agent_conn.row_factory = sqlite3.Row
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (step_id, step_id))
    rows = agent_cursor.fetchall()
    agent_cursor.close()
    agent_conn.close()
    if not rows:
        print(f"[DEBUG] No trade_records for step_id {step_id}.")
        return
    ctrl_cursor = ctrl_conn.cursor()
    print(f"[DEBUG] step_id {step_id} has {len(rows)} trade_records to sync.")
    print(f"[DEBUG] test_metrics_id: {test_metrics_id}")
    try:
        for idx, row in enumerate(rows):
            params = (test_metrics_id,) + tuple(row[col] for col in trade_record_columns)
            print(f"[DEBUG] trade_records Row {idx}: Param count: {len(params)}, First 3 values: {params[:3]}")
            if len(params) != 19:
                print(f"[ERROR] trade_records Row {idx}: Mismatch! Param count: {len(params)}, Placeholders: 19.")
            #print(f"[DEBUG] trade_records Row {idx}: Params: {params}, insert_sql: {insert_sql}")
            ctrl_cursor.execute(insert_sql, params)
            #print(f"[DEBUG] trade_records Row {idx} inserted with ID {ctrl_cursor.lastrowid}")
        print(f"[DEBUG] Copied {len(rows)} trade_records rows from agent step {step_id} to controller DB (test_metrics_id {test_metrics_id}).")
    except Exception as e:
        print(f"[ERROR] Error during sync_trade_records (step_id {step_id}): {e}")
        raise
    finally:
        ctrl_cursor.close()

def sync_test_metrics(worker_job_id, ctrl_conn):
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
        tm.optimization_pass_id,
        tm.step_id
    FROM set_file_jobs job
    JOIN set_file_steps steps ON steps.job_id = job.id
    JOIN test_metrics tm ON tm.step_id = steps.id
    WHERE job.id = ?
    """
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
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    target_columns = [
        'controller_task_id',
        'metric_type',
        'net_profit',
        'gross_profit',
        'gross_loss',
        'profit_factor',
        'expected_payoff',
        'max_drawdown',
        'max_drawdown_pct',
        'max_relative_drawdown',
        'max_relative_drawdown_pct',
        'absolute_drawdown',
        'initial_deposit',
        'total_trades',
        'profit_trades_pct',
        'loss_trades_pct',
        'largest_profit',
        'largest_loss',
        'recovery_factor',
        'sharpe_ratio',
        'sortino_ratio',
        'net_profit_per_initial_deposit',
        'absolute_drawdown_per_initial_deposit',
        'symbol',
        'period',
        'model',
        'bars_in_test',
        'ticks_modelled',
        'modelling_quality',
        'mismatched_charts_errors',
        'spread',
        'short_positions',
        'short_positions_won_pct',
        'long_positions',
        'long_positions_won_pct',
        'largest_profit_trade',
        'largest_loss_trade',
        'max_consecutive_wins',
        'max_consecutive_wins_profit',
        'max_consecutive_profit',
        'max_consecutive_profit_count',
        'max_consecutive_losses',
        'max_consecutive_losses_loss',
        'max_consecutive_loss',
        'max_consecutive_loss_count',
        'win_rate',
        'metrics_json',
        'parameters_json',
        'summary_csv',
        'created_at',
        'start_date',
        'end_date',
        'min_total_recovery',
        'min_trades',
        'min_max_drawdown',
        'criteria_passed',
        'criteria_reason',
        'set_file_name',
        'magic_number',
        'input_html_file',
        'input_set_file',
        'optimization_pass_id'
    ]
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    #agent_conn.execute(f"PRAGMA key = '{sqlcipher_key}';")
    agent_conn.row_factory = sqlite3.Row
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (worker_job_id,))
    rows = agent_cursor.fetchall()
    agent_cursor.close()
    agent_conn.close()
    if not rows:
        print(f"[DEBUG] No test_metrics found for worker_job_id {worker_job_id}.")
        return
    ctrl_cursor = ctrl_conn.cursor()
    try:
        for idx, row in enumerate(rows):
            params = tuple(row[col] for col in target_columns)
            print(f"[DEBUG] test_metrics Row {idx}: Columns used: {target_columns[:3]}... (total {len(target_columns)})")
            print(f"[DEBUG] test_metrics Row {idx}: Param count: {len(params)}, First 3 values: {params[:3]}")
            if len(params) != 62:
                print(f"[ERROR] test_metrics Row {idx}: Mismatch! Param count: {len(params)}, Placeholders: 62.")
            ctrl_cursor.execute(insert_sql, params)
            test_metrics_id = ctrl_cursor.lastrowid
            if 'step_id' in row.keys():
                sync_trade_records(row['step_id'], test_metrics_id, ctrl_conn)
        print(f"[DEBUG] Copied {len(rows)} test_metrics rows from agent job {worker_job_id} to controller DB.")
    except Exception as e:
        print(f"[ERROR] Error during sync_test_metrics: {e}")
        raise
    finally:
        ctrl_cursor.close()

def sync_artifacts(worker_job_id, ctrl_conn):
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
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    #agent_conn.execute(f"PRAGMA key = '{sqlcipher_key}';")
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(agent_sql, (worker_job_id,))
    rows = agent_cursor.fetchall()
    controller_task_id = rows[0][0] if rows else None
    agent_cursor.close()
    agent_conn.close()
    ctrl_cursor = ctrl_conn.cursor()
    try:
        for idx, row in enumerate(rows):
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
            params = (
                controller_task_id,
                artifact_type,
                file_path,
                file_name,
                meta_json,
                file_blob,
                link_type,
                link_id,
            )
            print(f"[DEBUG] controller_artifacts Row {idx}: Param count: {len(params)}, First 3 values: {params[:3]}")
            if len(params) != 8:
                print(f"[ERROR] controller_artifacts Row {idx}: Mismatch! Param count: {len(params)}, Placeholders: 8.")
            ctrl_cursor.execute(insert_sql, params)
        print(f"[DEBUG] Copied {len(rows)} artifact rows from agent job {worker_job_id} to controller DB.")
        if controller_task_id:
            #with controller_db_session() as session:
            #    link_artifacts_to_test_metrics_for_task(session, controller_task_id)
            link_artifacts_to_test_metrics_for_task(ctrl_conn, controller_task_id)
            print(f"[DEBUG] Linked artifacts to test_metrics for controller_task_id={controller_task_id}")
    except Exception as e:
        print(f"[ERROR] Error during artifact sync: {e}")
        raise
    finally:
        ctrl_cursor.close()

def sync_ai_suggestions(worker_job_id, ctrl_conn):
    import sqlite3
    agent_conn = sqlite3.connect(AGENT_DB_PATH)
    #agent_conn.execute(f"PRAGMA key = '{sqlcipher_key}';")
    agent_cursor = agent_conn.cursor()
    agent_cursor.execute(
        """
        SELECT
            sug.id,
            j.controller_job_id AS job_id,
            j.controller_task_id AS task_id,
            sug.mode,
            sug.created_at
        FROM set_file_jobs j
        JOIN set_file_steps s ON s.job_id = j.id
        JOIN optimization_suggestion sug ON sug.step_id = s.id
        WHERE j.id = ?
        """, (worker_job_id,)
    )
    suggestion_rows_raw = agent_cursor.fetchall()
    suggestion_rows = [
        (
            row[0],
            row[1],
            row[2],
            row[3] if row[3] is not None else "",
            "",
            row[4]
        )
        for row in suggestion_rows_raw
    ]
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
    agent_cursor.close()
    agent_conn.close()
    ctrl_cursor = ctrl_conn.cursor()
    try:
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
        for idx, row in enumerate(suggestion_rows):
            print(f"[DEBUG] controller_ai_suggestions Row {idx}: Param count: {len(row)}, First 3 values: {row[:3]}")
            if len(row) != 6:
                print(f"[ERROR] controller_ai_suggestions Row {idx}: Mismatch! Param count: {len(row)}, Placeholders: 6.")
            ctrl_cursor.execute(insert_suggestion_sql, row)
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
        for idx, row in enumerate(section_rows):
            print(f"[DEBUG] optimization_section Row {idx}: Param count: {len(row)}, First 3 values: {row[:3]}")
            if len(row) != 4:
                print(f"[ERROR] optimization_section Row {idx}: Mismatch! Param count: {len(row)}, Placeholders: 4.")
            ctrl_cursor.execute(insert_section_sql, row)
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
        for idx, row in enumerate(parameter_rows):
            print(f"[DEBUG] optimization_parameter Row {idx}: Param count: {len(row)}, First 3 values: {row[:3]}")
            if len(row) != 7:
                print(f"[ERROR] optimization_parameter Row {idx}: Mismatch! Param count: {len(row)}, Placeholders: 7.")
            ctrl_cursor.execute(insert_parameter_sql, row)
        print(f"[DEBUG] Copied {len(suggestion_rows)} suggestions, {len(section_rows)} sections, {len(parameter_rows)} parameters from agent job {worker_job_id} to controller DB.")
    except Exception as e:
        print(f"[ERROR] Error during AI suggestions sync: {e}")
        raise
    finally:
        ctrl_cursor.close()