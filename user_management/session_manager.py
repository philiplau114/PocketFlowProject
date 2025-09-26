import redis
import json
from datetime import datetime
import config

redis_client = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

def create_session(username, session_data):
    session_data['login_time'] = str(datetime.now())
    redis_client.setex(f"{config.SESSION_PREFIX}{username}", config.SESSION_TTL, json.dumps(session_data))

def get_session(username):
    data = redis_client.get(f"{config.SESSION_PREFIX}{username}")
    if data:
        return json.loads(data)
    return None

def update_session(username, session_data):
    session_data['last_update'] = str(datetime.now())
    redis_client.setex(f"{config.SESSION_PREFIX}{username}", config.SESSION_TTL, json.dumps(session_data))

def delete_session(username):
    redis_client.delete(f"{config.SESSION_PREFIX}{username}")

def is_authenticated(st_session_state):
    username = st_session_state.get("username")
    if not username:
        return False
    session_data = get_session(username)
    return session_data is not None

def sync_streamlit_session(st_session_state, username):
    session_data = get_session(username)
    if session_data:
        for key, value in session_data.items():
            st_session_state[key] = value