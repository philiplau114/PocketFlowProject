import streamlit as st
import sqlalchemy
import sys
import os
from datetime import datetime

# --- Import backend logic ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_utils import get_db, create_user, fetch_user_by_username
from db.db_models import User
import config
from session_manager import create_session, delete_session, get_session, is_authenticated, sync_streamlit_session

# --- STREAMLIT UI ---
st.set_page_config(page_title="Login / Registration", layout="centered")
st.markdown("<h1 style='text-align: center;'>Portfolio Lab Login / Registration</h1>", unsafe_allow_html=True)

tab_login, tab_register = st.tabs(["Login", "Register"])

with tab_login:
    st.subheader("Login")
    login_form = st.form("login_form")
    username = login_form.text_input("Username")
    password = login_form.text_input("Password", type="password")
    login_submit = login_form.form_submit_button("Login")

    if login_submit:
        db_session = get_db()
        user = fetch_user_by_username(db_session, username)
        if not user:
            st.error("User not found")
        elif user.status != "Approved":
            st.error("User not approved")
        elif not user.verify_password(password):
            st.error("Incorrect password")
        else:
            # Create session in Redis
            session_data = {
                "username": user.username,
                "user_id": user.id,
                "user_role": user.role,
                "open_router_api_key": user.open_router_api_key,
                "status": user.status
            }
            create_session(user.username, user.id, session_data)
            for k, v in session_data.items():
                st.session_state[k] = v
            st.success("Login successful!")
            if user.status != "Approved":
                st.info("Your account is awaiting admin approval.")
            else:
                st.info("You are logged in.")
            st.rerun()  # Force rerun so main.py shows sidebar

with tab_register:
    st.subheader("Register")
    reg_form = st.form("register_form")
    reg_username = reg_form.text_input("Username")
    reg_email = reg_form.text_input("Email")
    reg_password = reg_form.text_input("Password", type="password")
    reg_api_key = reg_form.text_input("OpenRouter API Key", type="password")
    reg_submit = reg_form.form_submit_button("Register")

    if reg_submit:
        db_session = get_db()
        if fetch_user_by_username(db_session, reg_username):
            st.error("Username already exists")
        else:
            password_hash = User.hash_password(reg_password)
            user_id = create_user(db_session, reg_username, reg_email, password_hash, reg_api_key)
            if user_id:
                st.success("Registration submitted! Please await admin approval.")
            else:
                st.error("Registration failed.")

# --- Show session info if logged in ---
if is_authenticated(st.session_state):
    sync_streamlit_session(st.session_state, st.session_state["username"])
    user = fetch_user_by_username(get_db(), st.session_state["username"])
    if user:
        st.info(f"Logged in as: {user.username} | Role: {user.role} | Status: {user.status}")
        logout_btn = st.button("Logout")
        if logout_btn:
            delete_session(st.session_state["username"])
            for key in ["username", "user_role", "open_router_api_key"]:
                st.session_state.pop(key, None)
            st.success("Logged out successfully!")
            st.rerun()  # Rerun so main.py shows only login/register

# st.markdown("""
# <div style='text-align: center; color: #999; margin-top:2em'>
#   &copy; 2025 PocketFlowProject. Powered by Streamlit.
# </div>
# """, unsafe_allow_html=True)