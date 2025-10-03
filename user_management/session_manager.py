import redis
import json
from datetime import datetime
import config

redis_client = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

def create_session(username, user_id, session_data):
    session_data['login_time'] = str(datetime.now())
    session_data['user_id'] = user_id
    session_data['username'] = username
    redis_client.setex(f"{config.SESSION_PREFIX}{username}", config.SESSION_TTL, json.dumps(session_data))

def get_session(username):
    data = redis_client.get(f"{config.SESSION_PREFIX}{username}")
    if data:
        session_data = json.loads(data)
        # Ensure both user_id and username are always present
        if "user_id" not in session_data or "username" not in session_data:
            return None
        return session_data
    return None

def update_session(username, user_id, session_data):
    session_data['last_update'] = str(datetime.now())
    session_data['user_id'] = user_id
    session_data['username'] = username
    redis_client.setex(f"{config.SESSION_PREFIX}{username}", config.SESSION_TTL, json.dumps(session_data))

def delete_session(username):
    redis_client.delete(f"{config.SESSION_PREFIX}{username}")

def is_authenticated(st_session_state):
    username = st_session_state.get("username")
    user_id = st_session_state.get("user_id")
    if not username or not user_id:
        return False
    session_data = get_session(username)
    return session_data is not None and session_data.get("user_id") == user_id

def sync_streamlit_session(st_session_state, username):
    session_data = get_session(username)
    if session_data:
        for key, value in session_data.items():
            st_session_state[key] = value