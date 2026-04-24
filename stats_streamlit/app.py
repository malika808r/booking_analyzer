import streamlit as st
from ui_utils import inject_custom_css, require_login, render_sidebar
from stats_sql import wait_for_db, get_conn

# --- HOME PAGE CONFIG ---
st.set_page_config(
    page_title="Booking Analyzer | Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto"
)

def main():
    inject_custom_css()
    
    # Wait for DB to be ready
    if not wait_for_db(get_conn):
        st.error("Could not connect to database after multiple retries. Please check your Docker containers.")
        st.stop()
    
    # Auto-bootstrap on startup if needed
    if "bootstrapped" not in st.session_state:
        from bootstrap_utils import run_bootstrap
        try:
            run_bootstrap()
        except Exception as e:
            st.error(f"Bootstrap failed: {e}")
        st.session_state.bootstrapped = True
    
    user = require_login()
    render_sidebar(user)

    st.title("Welcome to Booking Analyzer")
    st.write(f"Hello, **{user.role}**! Use the sidebar to navigate through insights and operations.")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Analytics")
            st.write("Track performance, peak hours, and AI-driven booking forecasts.")
            if st.button("Open Analytics", use_container_width=True):
                st.switch_page("pages/1_Analytics.py")
        
        with st.container(border=True):
            st.subheader("CRM & Guests")
            st.write("Analyze guest reliability, identify VIPs, and monitor No-Shows.")
            if st.button("Open CRM", use_container_width=True):
                st.switch_page("pages/3_CRM.py")

    with c2:
        with st.container(border=True):
            st.subheader("Tables")
            st.write("Manage your table inventory and guest capacity.")
            if st.button("Open Tables", use_container_width=True):
                st.switch_page("pages/2_Tables.py")
        
        with st.container(border=True):
            st.subheader("Staff")
            st.write("Manage team members and moderator permissions.")
            if st.button("Open Staff Management", use_container_width=True):
                if user.role == "OWNER":
                    st.switch_page("pages/4_Staff.py")
                else:
                    st.error("Admin only feature.")
        
        with st.container(border=True):
             st.subheader("Notifications")
             st.write("Recent activities and live booking alerts.")
             if st.button("Open Notifications", use_container_width=True):
                 st.switch_page("pages/5_Notifications.py")

if __name__ == "__main__":
    main()