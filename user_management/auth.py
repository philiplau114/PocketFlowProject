from db.db_models import User
from config import REDIS_HOST, REDIS_PORT
import uuid
import redis

# Use config.py for Redis connection details
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

SESSION_PREFIX = "session:"

def login(db_session, username, password):
    user = db_session.query(User).filter_by(username=username).first()
    if not user:
        return None, "User not found"
    if user.status != "Approved":
        return None, "User not approved"
    if not user.verify_password(password):
        return None, "Incorrect password"
    session_token = str(uuid.uuid4())
    # Store session in Redis with a 1-day (86400 sec) expiry
    redis_client.setex(SESSION_PREFIX + session_token, 86400, username)
    return session_token, None

def logout(session_token):
    """Logs out a user by removing their session token from Redis."""
    redis_client.delete(SESSION_PREFIX + session_token)
    return True

def get_active_sessions():
    """Returns a list of currently logged-in usernames."""
    sessions = []
    for key in redis_client.scan_iter(SESSION_PREFIX + "*"):
        username = redis_client.get(key)
        if username:
            sessions.append(username.decode())
    return sessions