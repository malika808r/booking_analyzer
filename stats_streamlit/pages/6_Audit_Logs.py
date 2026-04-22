import streamlit as st
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_audit_logs

def main():
    st.set_page_config(page_title="Booking Analyzer | Audit Logs", page_icon="📜", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    rid = st.session_state.get("selected_restaurant_id")

    if not rid:
        st.warning("Please select a restaurant to view audit logs.")
        return

    st.title("📜 System Audit Logs")
    st.caption("Administrative activity history for restaurant security Compliance")
    st.markdown("---")

    df_logs = get_audit_logs(rid)

    if df_logs.empty:
        st.info("No administrative actions have been recorded yet.")
    else:
        # Display logs in a nice searchable dataframe
        st.dataframe(
            df_logs,
            use_container_width=True,
            column_config={
                "Time": st.column_config.DatetimeColumn("Event Time", format="D MMM YYYY, HH:mm"),
                "User": st.column_config.TextColumn("Actor"),
                "Action": st.column_config.TextColumn("Action Type"),
                "Details": st.column_config.TextColumn("Detailed Description"),
            }
        )
        
        st.download_button(
            label="📥 Download Audit Report (CSV)",
            data=df_logs.to_csv(index=False).encode('utf-8'),
            file_name=f"audit_log_{rid}.csv",
            mime="text/csv",
        )

if __name__ == "__main__":
    main()
