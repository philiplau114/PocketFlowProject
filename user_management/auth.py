from db_utils import get_db, fetch_user_by_username, fetch_user_by_id, log_action
from db_models import User
import uuid

active_sessions = {}

def login(username, password):
    session = get_db()
    user = fetch_user_by_username(session, username)
    if not user:
        return None, "User not found"
    if user.status != 'Approved':
        return None, "User not approved"
    if not User.verify_password(password, user.password_hash):
        return None, "Invalid password"
    if user.id in active_sessions:
        return None, "User already has an active session"
    session_token = str(uuid.uuid4())
    active_sessions[user.id] = session_token
    log_action(session, user.id, "Login", details={"session_token": session_token})
    return session_token, None

def logout(user_id):
    session = get_db()
    if user_id in active_sessions:
        log_action(session, user_id, "Logout", details={"session_token": active_sessions[user_id]})
        del active_sessions[user_id]
        return True
    return False

def get_user_from_session(token):
    session = get_db()
    for user_id, sess_token in active_sessions.items():
        if sess_token == token:
            return fetch_user_by_id(session, user_id)
    return None