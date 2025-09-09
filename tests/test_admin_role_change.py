from db.db_models import User
from db_utils import create_user, change_user_role, fetch_user_by_id, log_action, get_audit_log

def test_role_change_and_audit(db_session):
    password_hash = User.hash_password("adminrole")
    user_id = create_user(db_session, "adminuser", "admin@email.com", password_hash)
    # Change role
    admin_id = user_id
    change_user_role(db_session, user_id, "admin", admin_id)
    user = fetch_user_by_id(db_session, user_id)
    assert user.role == "admin"
    # Audit log
    logs = get_audit_log(db_session, user_id=admin_id)
    assert any(log.action == "Role Changed" for log in logs)