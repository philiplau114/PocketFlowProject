import streamlit as st
import sqlalchemy
import redis
import uuid
import bcrypt
import sys
import os
from datetime import datetime

# --- Import backend logic ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_utils import get_db, create_user, fetch_user_by_username
from db.db_models import User
from config import REDIS_HOST, REDIS_PORT

# --- REDIS SESSION ---
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
SESSION_PREFIX = "session:"

def login_backend(username, password):
    db_session = get_db()
    user = fetch_user_by_username(db_session, username)
    if not user:
        return None, "User not found"
    if user.status != "Approved":
        return None, "User not approved"
    if not user.verify_password(password):
        return None, "Incorrect password"
    session_token = str(uuid.uuid4())
    redis_client.setex(SESSION_PREFIX + session_token, 86400, username)
    return session_token, None

def register_backend(username, email, password, api_key):
    db_session = get_db()
    if fetch_user_by_username(db_session, username):
        return None, "Username already exists"
    password_hash = User.hash_password(password)
    user_id = create_user(db_session, username, email, password_hash, api_key)
    return user_id, None

def get_user_by_token(session_token):
    username = redis_client.get(SESSION_PREFIX + session_token)
    if username:
        db_session = get_db()
        return fetch_user_by_username(db_session, username.decode())
    return None

# --- STREAMLIT UI ---
st.set_page_config(page_title="Login / Registration", layout="centered")
st.markdown("<h1 style='text-align: center;'>PocketFlow Login / Registration</h1>", unsafe_allow_html=True)

tab_login, tab_register = st.tabs(["Login", "Register"])

with tab_login:
    st.subheader("Login")
    login_form = st.form("login_form")
    username = login_form.text_input("Username")
    password = login_form.text_input("Password", type="password")
    login_submit = login_form.form_submit_button("Login")

    if login_submit:
        session_token, error = login_backend(username, password)
        if session_token:
            st.session_state["session_token"] = session_token
            st.success("Login successful!")
            st.info("Your account is awaiting admin approval." if get_user_by_token(session_token).status != "Approved" else "You are logged in.")
        else:
            st.error(error)

with tab_register:
    st.subheader("Register")
    reg_form = st.form("register_form")
    reg_username = reg_form.text_input("Username")
    reg_email = reg_form.text_input("Email")
    reg_password = reg_form.text_input("Password", type="password")
    reg_api_key = reg_form.text_input("OpenRouter API Key", type="password")
    reg_submit = reg_form.form_submit_button("Register")

    if reg_submit:
        user_id, error = register_backend(reg_username, reg_email, reg_password, reg_api_key)
        if user_id:
            st.success("Registration submitted! Please await admin approval.")
        else:
            st.error(error)

# --- Show session info if logged in ---
if "session_token" in st.session_state:
    user = get_user_by_token(st.session_state["session_token"])
    if user:
        st.info(f"Logged in as: {user.username} | Role: {user.role} | Status: {user.status}")
        logout_btn = st.button("Logout")
        if logout_btn:
            redis_client.delete(SESSION_PREFIX + st.session_state["session_token"])
            st.session_state.pop("session_token")
            st.success("Logged out successfully!")

st.markdown("""
<div style='text-align: center; color: #999; margin-top:2em'>
  &copy; 2025 PocketFlowProject. Powered by Streamlit.
</div>
""", unsafe_allow_html=True)