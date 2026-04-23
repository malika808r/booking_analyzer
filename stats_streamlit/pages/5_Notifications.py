import streamlit as st
import pandas as pd
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_latest_bookings

def main():
    st.set_page_config(page_title="Booking Analyzer | Notifications", page_icon="🔔", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)

    rid = st.session_state.get("selected_restaurant_id")
    if not rid:
        st.warning("Please select a restaurant to view notifications.")
        return

    st.title("🔔 Live Notifications")
    st.caption("Real-time booking events and history")
    st.markdown("---")

    # --- REFRESH BUTTON ---
    if st.button("🔄 Check for New Bookings", use_container_width=True):
        st.rerun()

    df = get_latest_bookings(rid)

    if df.empty:
        st.info("No recent bookings found.")
    else:
        for _, row in df.iterrows():
            # Choose color based on status
            status = row['status']
            if status == 'CANCELLED':
                icon = "❌"
                color = "#ff4b4b"
            elif status == 'NO_SHOW':
                icon = "⚠️"
                color = "#ffa500"
            elif status == 'BOOKED':
                icon = "🔔"
                color = "#ffd700"
            else:
                icon = "✅"
                color = "#28a745"

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 4, 3, 2])
                c1.markdown(f"### {icon}")
                
                with c2:
                    st.markdown(f"**{row['customer_name']}**")
                    st.caption(f"Created: {row['created_at'].strftime('%H:%M:%S, %d %b')}")
                
                with c3:
                    st.write(f"📅 Plan: **{row['start_time'].strftime('%H:%M, %d %b')}**")
                    st.write(f"👥 Guests: **{row['party_size']}**")
                
                with c4:
                    st.markdown(f"<p style='color:{color}; font-weight:bold; margin-top:10px;'>{status}</p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
