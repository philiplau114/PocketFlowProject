from db_utils import get_db, get_audit_log

def get_audit_log_for_user(user_id=None, limit=100):
    session = get_db()
    return get_audit_log(session, user_id=user_id, limit=limit)