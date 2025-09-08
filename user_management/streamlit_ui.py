import streamlit as st
from db_models import User
from db_utils import get_db, create_user, fetch_user_by_username
from user_management.auth import login, logout, active_sessions
from user_management.admin import approve_user, deny_user, change_role
from user_management.audit import get_audit_log_for_user

def registration_page():
    st.title("User Registration")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        session = get_db()
        if fetch_user_by_username(session, username):
            st.error("Username already exists.")
        else:
            password_hash = User.hash_password(password)
            user_id = create_user(session, username, email, password_hash)
            st.success("Registration complete! Awaiting admin approval.")

def login_page():
    st.title("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        session_token, error = login(username, password)
        if session_token:
            st.success("Login successful!")
            st.session_state['session_token'] = session_token
        else:
            st.error(error)

def admin_approval_page(admin_id):
    st.title("Admin User Approval")
    # Example code: fetch pending users and show approval buttons
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

# In your Streamlit main app, import and call these functions as pages.