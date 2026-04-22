import streamlit as st
from ui_utils import inject_custom_css, require_login, render_sidebar
from stats_sql import wait_for_db, get_conn

# --- HOME PAGE CONFIG ---
st.set_page_config(
    page_title="Booking Analyzer | Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
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

    st.title("🚀 Welcome to Booking Analyzer")
    st.write(f"Hello, **{user.role}**! Use the sidebar to navigate through insights and menu management.")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("📈 Analytics")
            st.write("Track your restaurant's performance, peak hours, and booking dynamics.")
            if st.button("Open Analytics", use_container_width=True):
                st.switch_page("pages/1_Analytics.py")

    with col2:
        with st.container(border=True):
            st.subheader("🍴 Menu Management")
            st.write("Update your menu items, categories, and availability in real-time.")
            if st.button("Open Menu", use_container_width=True):
                st.switch_page("pages/2_Menu.py")

if __name__ == "__main__":
    main()