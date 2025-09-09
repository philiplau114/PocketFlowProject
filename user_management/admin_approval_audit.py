import streamlit as st
import sys
import os
from datetime import datetime

# Ensure root and db folder are in Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_utils import get_db, fetch_user_by_id, update_user_status, change_user_role, log_action, get_audit_log, fetch_user_by_username
from db.db_models import User, AuditLog

st.set_page_config(page_title="Admin Approval & Audit Log", layout="wide")
st.markdown("<h1 style='text-align: center;'>Admin Approval & Audit Log</h1>", unsafe_allow_html=True)

# -- Helper: Check if current user is admin --
def is_admin(session_state):
    session_token = session_state.get("session_token")
    if not session_token:
        return False, None
    db_session = get_db()
    username = session_state.get("username")
    user = fetch_user_by_username(db_session, username)
    return user and user.role == "Admin", user

# -- Admin Login Section (simple for demo) --
if "session_token" not in st.session_state or "username" not in st.session_state:
    with st.form("admin_login_form"):
        username = st.text_input("Admin Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login as Admin")
    if submit:
        db_session = get_db()
        user = fetch_user_by_username(db_session, username)
        if user and user.role == "Admin" and user.verify_password(password) and user.status == "Approved":
            st.session_state["session_token"] = f"admin-{user.id}"  # For demo; use your session logic here
            st.session_state["username"] = username
            st.success("Logged in as Admin.")
            st.rerun()
        else:
            st.error("Invalid admin credentials or not approved.")
    st.stop()

is_admin_user, admin_user = is_admin(st.session_state)
if not is_admin_user:
    st.error("You must be logged in as an approved admin to access this page.")
    st.stop()

# -- 1. User Approval Section --
st.subheader("Pending User Approvals")
db_session = get_db()
pending_users = db_session.query(User).filter(User.status == "Pending").all()

if pending_users:
    for user in pending_users:
        with st.expander(f"User: {user.username} ({user.email})", expanded=False):
            st.write(f"**Registered:** {user.date_registered.strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"**Role Requested:** {user.role}")
            st.write(f"**Status:** {user.status}")
            approve_btn, deny_btn = st.columns(2)
            if approve_btn.button("Approve", key=f"approve_{user.id}"):
                update_user_status(db_session, user.id, "Approved", approved_by=admin_user.id)
                log_action(db_session, admin_user.id, "User Approved", target_id=user.id)
                st.success(f"{user.username} approved.")
                st.rerun()
            if deny_btn.button("Deny", key=f"deny_{user.id}"):
                update_user_status(db_session, user.id, "Denied", approved_by=admin_user.id)
                log_action(db_session, admin_user.id, "User Denied", target_id=user.id)
                st.warning(f"{user.username} denied.")
                st.rerun()
else:
    st.info("No pending users for approval.")

# -- 2. Audit Log Section --
st.subheader("Audit Log")
audit_limit = st.slider("Audit log entries to show:", min_value=10, max_value=200, value=50)
audit_logs = get_audit_log(db_session, limit=audit_limit)

if audit_logs:
    log_table = []
    for log in audit_logs:
        user = fetch_user_by_id(db_session, log.user_id)
        log_table.append({
            "Timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "Admin": user.username if user else str(log.user_id),
            "Action": log.action,
            "Target": log.target_id,
            "Details": str(log.details)
        })
    st.dataframe(log_table)
else:
    st.info("No audit log entries found.")

st.markdown("""
<div style='text-align: center; color: #999; margin-top:2em'>
  &copy; 2025 PocketFlowProject. Powered by Streamlit.
</div>
""", unsafe_allow_html=True)