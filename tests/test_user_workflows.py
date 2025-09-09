import pytest
from db.db_models import User
from db_utils import create_user, fetch_user_by_username, fetch_user_by_id, update_user_status, log_action, get_audit_log

def test_register_user(db_session):
    # Register a user
    password = "testpass"
    password_hash = User.hash_password(password)
    user_id = create_user(db_session, "tester", "tester@email.com", password_hash)
    user = fetch_user_by_id(db_session, user_id)
    assert user is not None
    assert user.username == "tester"
    assert user.status == "Pending"
    assert user.verify_password(password)  # <-- FIXED

def test_duplicate_username(db_session):
    password_hash = User.hash_password("abc123")
    create_user(db_session, "dupuser", "dup@email.com", password_hash)
    # Try duplicate
    with pytest.raises(Exception):
        create_user(db_session, "dupuser", "another@email.com", password_hash)

def test_approve_user(db_session):
    password_hash = User.hash_password("adminpass")
    user_id = create_user(db_session, "pendinguser", "pending@email.com", password_hash)
    update_user_status(db_session, user_id, "Approved", approved_by=999)
    user = fetch_user_by_id(db_session, user_id)
    assert user.status == "Approved"
    assert user.approved_by == 999
    assert user.date_approved is not None

def test_log_action_and_audit(db_session):
    password_hash = User.hash_password("audittest")
    user_id = create_user(db_session, "audituser", "audit@email.com", password_hash)
    log_action(db_session, user_id, "Login", details={"info": "test"})
    logs = get_audit_log(db_session, user_id=user_id)
    assert logs
    assert logs[0].action == "Login"
    assert logs[0].details["info"] == "test"