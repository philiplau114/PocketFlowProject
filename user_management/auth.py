from user_management.models import User
from user_management.db_utils import fetch_user_by_username, log_action
import uuid

# You can extend this with a persistent session table if needed
active_sessions = {}

def login(username, password):
    user = fetch_user_by_username(username)
    if not user:
        return None, "User not found"
    if user['status'] != 'Approved':
        return None, "User not approved"
    if not User.verify_password(password, user['password_hash']):
        return None, "Invalid password"
    # Ensure only one session per user
    if user['id'] in active_sessions:
        return None, "User already has an active session"
    session_token = str(uuid.uuid4())
    active_sessions[user['id']] = session_token
    log_action(user['id'], "Login", details={"session_token": session_token})
    return session_token, None

def logout(user_id):
    if user_id in active_sessions:
        log_action(user_id, "Logout", details={"session_token": active_sessions[user_id]})
        del active_sessions[user_id]
        return True
    return False

def get_user_from_session(token):
    for user_id, sess_token in active_sessions.items():
        if sess_token == token:
            return fetch_user_by_id(user_id)
    return None