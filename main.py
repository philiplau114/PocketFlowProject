import streamlit as st
import importlib.util
import os

def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# --- Session & Role Helpers ---
def get_logged_in_user():
    return st.session_state.get("session_token", None)

def get_current_user_role():
    # Should be 'Admin', 'Standard', or 'Guest'
    return st.session_state.get("user_role", None)

def is_admin():
    return get_current_user_role() == "Admin"

def is_logged_in():
    return get_logged_in_user() is not None

def is_standard_user():
    return get_current_user_role() == "Standard" or get_current_user_role() == "Trader"

# --- Page Choices ---
st.set_page_config(page_title="PocketFlow Main", layout="centered")
st.title("PocketFlow Project")
st.markdown("Welcome to PocketFlow! Select a page from the navigation below:")

# Sidebar and logout enhancement
if is_logged_in():
    with st.sidebar:
        options = [
            "Strategy Dashboard",
            "Portfolio Management",
            "Portfolio Reviewer (AI)",  # NEW PAGE
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
            st.session_state.pop("session_token", None)
            st.session_state.pop("username", None)
            st.session_state.pop("user_role", None)
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
  &copy; 2025 PocketFlowProject. Powered by Streamlit.
</div>
""", unsafe_allow_html=True)