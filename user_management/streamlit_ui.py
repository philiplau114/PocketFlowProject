import streamlit as st
from user_management.auth import login, logout, active_sessions
from user_management.db_utils import create_user, fetch_user_by_username
from user_management.admin import approve_user, deny_user, change_role
from user_management.audit import get_audit_log

def registration_page():
    st.title("User Registration")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        if fetch_user_by_username(username):
            st.error("Username already exists.")
        else:
            password_hash = User.hash_password(password)
            user_id = create_user(username, email, password_hash)
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
    # Fetch pending users
    # ... (code to show pending users, approve/deny buttons)
    # Use approve_user, deny_user functions

def audit_log_page():
    st.title("Audit Log")
    logs = get_audit_log()
    for log in logs:
        st.write(log)

# In your Streamlit main app, import and call these functions as pages.