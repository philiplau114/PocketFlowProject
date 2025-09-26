import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from db.db_models import User
from db_utils import get_db, create_user, fetch_user_by_username
from user_management.auth import login, logout, get_active_sessions
from user_management.admin import approve_user, deny_user, change_role
from user_management.audit import get_audit_log_for_user
from session_manager import create_session, delete_session, is_authenticated, sync_streamlit_session

def registration_page():
    st.title("User Registration")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    open_router_api_key = st.text_input("OpenRouter API Key", type="password")

    if st.button("Register"):
        session = get_db()
        if fetch_user_by_username(session, username):
            st.error("Username already exists.")
        else:
            password_hash = User.hash_password(password)
            user_id = create_user(
                session,
                username,
                email,
                password_hash,
                open_router_api_key=open_router_api_key
            )
            st.success("Registration complete! Awaiting admin approval.")

def login_page():
    st.title("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        session = get_db()
        session_token, error = login(session, username, password)
        if session_token:
            # Use unified session management
            user = fetch_user_by_username(session, username)
            session_data = {
                "username": user.username,
                "user_role": user.role,
                "open_router_api_key": user.open_router_api_key,
                "status": user.status
            }
            create_session(user.username, session_data)
            for k, v in session_data.items():
                st.session_state[k] = v
            st.success("Login successful!")
            st.rerun()
        else:
            st.error(error)

def admin_approval_page(admin_id):
    st.title("Admin User Approval")
    session = get_db()
    pending_users = session.query(User).filter_by(status='Pending').all()
    for user in pending_users:
        st.write(f"{user.username} ({user.email})")
        if st.button(f"Approve {user.username}"):
            approve_user(user.id, admin_id)
            st.success(f"Approved {user.username}")
        if st.button(f"Deny {user.username}"):
            deny_user(user.id, admin_id)
            st.success(f"Denied {user.username}")

def audit_log_page():
    st.title("Audit Log")
    session = get_db()
    logs = get_audit_log_for_user()
    for log in logs:
        st.write(log)

def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "Register",
        "Login",
        "Admin Approval",
        "Audit Log"
    ])
    if page == "Register":
        registration_page()
    elif page == "Login":
        login_page()
    elif page == "Admin Approval":
        admin_id = st.session_state.get("admin_id", "admin_test")
        admin_approval_page(admin_id)
    elif page == "Audit Log":
        audit_log_page()

if __name__ == "__main__" or st.session_state.get("run_main", True):
    main()