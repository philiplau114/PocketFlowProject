import streamlit as st
import importlib.util
import os
import config
from user_management.session_manager import is_authenticated, sync_streamlit_session, delete_session

def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# --- Session & Role Helpers (Unified) ---
def get_logged_in_user():
    return st.session_state.get("username", None)

def get_current_user_role():
    # Should be 'Admin', 'Standard', or 'Guest'
    return st.session_state.get("user_role", None)

def is_admin():
    return get_current_user_role() == "Admin"

def is_logged_in():
    # Use unified session management
    return is_authenticated(st.session_state)

def is_standard_user():
    return get_current_user_role() == "Standard" or get_current_user_role() == "Trader"

# --- Page Choices ---
st.set_page_config(page_title="Portfolio Lab Main", layout="centered")
st.title("Portfolio Lab")
st.markdown("Intelligent automation for algorithmic portfolios.")

# Sync Streamlit session with Redis if logged in
if is_logged_in():
    sync_streamlit_session(st.session_state, st.session_state.get("username"))

    with st.sidebar:
        options = [
            "Strategy Dashboard",
            "Portfolio Management",
            "Portfolio Reviewer (AI)",
            "Optimization Dashboard",  # <-- Added here
            "Settings / Profile"
        ]
        if is_admin():
            options += ["Controller Dashboard", "Admin Approval / Audit Log"]
        page = st.radio("Go to page:", options)
        st.write("---")
        st.write(f"**Logged in as:** `{st.session_state.get('username', '')}`")
        logout_btn = st.button("Logout", key="sidebar_logout")
        if logout_btn:
            # Remove session state keys and force rerun to return to login
            delete_session(st.session_state.get("username"))
            for key in ["username", "user_role", "open_router_api_key"]:
                st.session_state.pop(key, None)
            st.success("Logged out successfully!")
            st.rerun()
else:
    page = "Login / Registration"

# --- Page Routing ---
if page == "Login / Registration":
    st.query_params["page"] = "login_registration"
    with st.spinner("Loading Login / Registration..."):
        import_module_from_file("login_registration", os.path.join("user_management", "login_registration.py"))

elif page == "Strategy Dashboard":
    st.query_params["page"] = "strategy_dashboard"
    with st.spinner("Loading Strategy Dashboard..."):
        import_module_from_file("strategy_dashboard", os.path.join("streamlit", "strategy_dashboard.py"))

elif page == "Portfolio Management":
    if not is_standard_user():
        st.error("You must be a Standard/Trader user to access this page.")
    else:
        st.query_params["page"] = "portfolio_management"
        with st.spinner("Loading Portfolio Management..."):
            import_module_from_file("portfolio_management", os.path.join("user_management", "portfolio_management.py"))

elif page == "Portfolio Reviewer (AI)":
    if not is_standard_user():
        st.error("You must be a Standard/Trader user to access this page.")
    else:
        st.query_params["page"] = "portfolio_reviewer_app"
        with st.spinner("Loading Portfolio Reviewer (AI)..."):
            import_module_from_file(
                "portfolio_reviewer_app",
                os.path.join("portfolio_analysis", "portfolio_reviewer_app_gpt4o.py")
            )

elif page == "Optimization Dashboard":
    if not is_standard_user():
        st.error("You must be a Standard/Trader user to access this page.")
    else:
        st.query_params["page"] = "optimization_dashboard"
        with st.spinner("Loading Optimization Dashboard..."):
            import_module_from_file(
                "optimization_dashboard",
                os.path.join("streamlit", "optimization_dashboard.py")
            )

elif page == "Settings / Profile":
    st.query_params["page"] = "settings_profile"
    with st.spinner("Loading Settings / Profile..."):
        import_module_from_file("settings_profile", os.path.join("user_management", "settings_profile.py"))

elif page == "Controller Dashboard":
    if not is_admin():
        st.error("You must be an admin to access this page.")
    else:
        st.query_params["page"] = "controller_dashboard"
        with st.spinner("Loading Controller Dashboard..."):
            import_module_from_file("controller_dashboard", os.path.join("streamlit", "controller_dashboard.py"))

elif page == "Admin Approval / Audit Log":
    if not is_admin():
        st.error("You must be an admin to access this page.")
    else:
        st.query_params["page"] = "admin_approval_audit"
        with st.spinner("Loading Admin Approval / Audit Log..."):
            import_module_from_file("admin_approval_audit", os.path.join("user_management", "admin_approval_audit.py"))

st.markdown("""
<div style='text-align: center; color: #999; margin-top:2em'>
  &copy; 2025 Portfolio Lab. Powered by Streamlit.
</div>
""", unsafe_allow_html=True)