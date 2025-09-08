from user_management.db_utils import get_db_connection

def get_audit_log(user_id=None, limit=100):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if user_id:
        cursor.execute("SELECT * FROM audit_log WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s", (user_id, limit))
    else:
        cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT %s", (limit,))
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return logs