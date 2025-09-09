import streamlit as st
from db_utils import get_db, fetch_user_by_username, set_open_router_api_key
import redis
import config

# --- CONFIG ---
REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Settings / Profile", layout="centered")
st.title("⚙️ Settings & Profile")

# --- AUTH CHECK ---
username = st.session_state.get("username")
if not username:
    st.warning("You must be logged in to view this page.")
    st.stop()

session = get_db()
user = fetch_user_by_username(session, username)

if not user:
    st.error("User profile not found.")
    st.stop()

# --- Settings Form ---
with st.form("profile_form", clear_on_submit=False):
    st.subheader("Profile Info")
    st.text_input("Username", value=user.username, disabled=True)
    email = st.text_input("Email", value=user.email if user.email else "")
    st.text_input("Role", value=getattr(user, "role", getattr(user, "user_role", "")), disabled=True)
    st.text_input("Member since", value=str(getattr(user, "date_registered", getattr(user, "created_at", ""))), disabled=True)

    st.markdown("---")
    st.subheader("Change Password")
    new_password = st.text_input("New Password", type="password")
    new_password_confirm = st.text_input("Confirm New Password", type="password")
    change_pw_btn = st.form_submit_button("Update Profile")

if change_pw_btn:
    update_msg = ""
    # Update email
    if email and email != user.email:
        user.email = email
        session.commit()
        update_msg += "Email updated. "

    # Update password
    if new_password:
        if new_password != new_password_confirm:
            st.error("Passwords do not match.")
        elif len(new_password) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            # Store plain password for demo; in prod, hash!
            user.password_hash = new_password
            session.commit()
            update_msg += "Password updated. "
    if update_msg:
        st.success(update_msg)
        st.experimental_rerun()

# --- API Key Settings ---
st.markdown("---")
st.subheader("OpenRouter API Key")
api_key = getattr(user, "open_router_api_key", None) or st.session_state.get("open_router_api_key") or r.get(f"user:{username}:open_router_api_key") or ""

api_key_input = st.text_input("OpenRouter API Key", value=api_key, type="password")
if st.button("Save API Key"):
    # Save to both SQL and Redis for compatibility
    set_open_router_api_key(session, username, api_key_input)
    r.set(f"user:{username}:open_router_api_key", api_key_input)
    st.session_state["open_router_api_key"] = api_key_input
    st.success("API Key updated.")

st.markdown("---")
if st.button("Logout"):
    st.session_state.clear()
    st.success("Logged out. Please reload or go to Login page.")
    st.stop()

st.caption("Update your profile info, password, and OpenRouter API key securely. If you want to change your role, contact admin.")