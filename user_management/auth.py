from db.db_models import User
import config
import redis
import json
from session_manager import create_session, delete_session, get_session

# Use config.py for Redis connection details
redis_client = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

def login(db_session, username, password):
    user = db_session.query(User).filter_by(username=username).first()
    if not user:
        return None, "User not found"
    if user.status != "Approved":
        return None, "User not approved"
    if not user.verify_password(password):
        return None, "Incorrect password"
    # Store session in Redis using unified session manager
    session_data = {
        "username": username,
        "user_role": user.role
    }
    create_session(username, session_data)
    return username, None  # Return username as session key

def logout(username):
    """Logs out a user by removing their session from Redis."""
    delete_session(username)
    return True

def get_active_sessions():
    """Returns a list of currently logged-in usernames."""
    sessions = []
    for key in redis_client.scan_iter(f"{config.SESSION_PREFIX}*"):
        session_data = redis_client.get(key)
        if session_data:
            try:
                data = json.loads(session_data)
                username = data.get("username")
                if username:
                    sessions.append(username)
            except Exception:
                pass
    return sessions