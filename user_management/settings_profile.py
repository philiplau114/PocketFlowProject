import streamlit as st
from db_utils import get_db, fetch_user_by_username, set_open_router_api_key
import redis
import config
from session_manager import is_authenticated, sync_streamlit_session

r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)

# --- UI Enhancement: Full-width layout and custom CSS --- 
st.set_page_config(page_title="Settings / Profile", layout="centered")
st.markdown(
    """
    <style>
    .block-container { max-width: 100% !important; padding: 2rem 2rem 2rem 2rem; }
    .element-container { width: 100% !important; }
    .stDataFrame, .stSelectbox, .stDataEditor, .stTextInput, .stForm { width: 100% !important; }
    .stButton button { width: 100%; }
    .stTextInput input { width: 100%; }
    .stTextArea textarea { width: 100%; }
    .stForm { box-shadow: 0 2px 12px rgba(0,0,0,0.06); border-radius: 0.5rem; padding: 2rem; background: #fafbfc; }
    .stForm .stButton { margin-top: 1em; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("⚙️ Settings & Profile")

if not is_authenticated(st.session_state):
    st.warning("You must be logged in to view this page.")
    st.stop()
sync_streamlit_session(st.session_state, st.session_state["username"])
username = st.session_state.get("username")

session = get_db()
user = fetch_user_by_username(session, username)

if not user:
    st.error("User profile not found.")
    st.stop()

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
    if email and email != user.email:
        user.email = email
        session.commit()
        update_msg += "Email updated. "

    if new_password:
        if new_password != new_password_confirm:
            st.error("Passwords do not match.")
        elif len(new_password) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            user.password_hash = new_password
            session.commit()
            update_msg += "Password updated. "
    if update_msg:
        st.success(update_msg)
        st.rerun()

st.markdown("---")
st.subheader("OpenRouter API Key")
api_key = getattr(user, "open_router_api_key", None) or st.session_state.get("open_router_api_key") or r.get(f"user:{username}:open_router_api_key") or ""

api_key_input = st.text_input("OpenRouter API Key", value=api_key, type="password")
if st.button("Save API Key"):
    set_open_router_api_key(session, username, api_key_input)
    r.set(f"user:{username}:open_router_api_key", api_key_input)
    st.session_state["open_router_api_key"] = api_key_input
    st.success("API Key updated.")

st.markdown("---")
if st.button("Logout"):
    from session_manager import delete_session
    delete_session(username)
    for key in ["username", "user_role", "open_router_api_key"]:
        st.session_state.pop(key, None)
    st.success("Logged out. Please reload or go to Login page.")
    st.stop()

st.caption("Update your profile info, password, and OpenRouter API key securely. If you want to change your role, contact admin.")