from user_management.db_utils import fetch_user_by_id, update_user_status, log_action

def approve_user(user_id, admin_id):
    update_user_status(user_id, "Approved", approved_by=admin_id)
    log_action(admin_id, "User Approved", target_id=user_id)

def deny_user(user_id, admin_id):
    update_user_status(user_id, "Denied", approved_by=admin_id)
    log_action(admin_id, "User Denied", target_id=user_id)

def change_role(user_id, new_role, admin_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    log_action(admin_id, "Role Changed", target_id=user_id, details={"new_role": new_role})