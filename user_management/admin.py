from db_utils import get_db, fetch_user_by_id, update_user_status, change_user_role, log_action

def approve_user(user_id, admin_id):
    session = get_db()
    update_user_status(session, user_id, "Approved", approved_by=admin_id)
    log_action(session, admin_id, "User Approved", target_id=user_id)

def deny_user(user_id, admin_id):
    session = get_db()
    update_user_status(session, user_id, "Denied", approved_by=admin_id)
    log_action(session, admin_id, "User Denied", target_id=user_id)

def change_role(user_id, new_role, admin_id):
    session = get_db()
    change_user_role(session, user_id, new_role, admin_id)