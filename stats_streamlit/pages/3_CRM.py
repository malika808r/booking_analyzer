import streamlit as st
import pandas as pd
import plotly.express as px
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_customer_metrics

def main():
    st.set_page_config(page_title="Booking Analyzer | Customer Insights", page_icon="👥", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    rid = st.session_state.get("selected_restaurant_id")

    if not rid:
        st.warning("Please select a restaurant to view customer insights.")
        return

    st.title("👥 Customer Insights & Segmentation")
    st.caption("Behavioral analysis using RFM-like reliability metrics")
    st.markdown("---")

    df = get_customer_metrics(rid)
    
    if df.empty:
        st.info("No customer data available yet. Start taking bookings to see insights!")
        return

    # Data Processing for Segmentation
    df['reliability'] = (df['completed'] / df['total_bookings'] * 100).round(1)
    
    def segment_customer(row):
        if row['completed'] >= 5 and row['flakes'] == 0:
            return "💎 VIP"
        if row['flakes'] >= 2 or (row['total_bookings'] > 2 and row['reliability'] < 70):
            return "⚠️ At Risk"
        if row['total_bookings'] >= 3:
            return "📈 Loyal"
        return "✨ New"

    df['Segment'] = df.apply(segment_customer, axis=1)

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Customers", len(df))
    m2.metric("VIP Guests", len(df[df['Segment'] == "💎 VIP"]))
    m3.metric("At Risk", len(df[df['Segment'] == "⚠️ At Risk"]), delta_color="inverse")
    m4.metric("Avg Reliability", f"{df['reliability'].mean():.1f}%")

    st.write("### 📊 Guest Reliability Map")
    fig = px.scatter(
        df, 
        x="total_bookings", 
        y="reliability",
        color="Segment",
        size="total_bookings",
        hover_name="name",
        labels={"total_bookings": "Total Bookings", "reliability": "Reliability (%)"},
        color_discrete_map={"💎 VIP": "#FFD700", "📈 Loyal": "#00CC96", "✨ New": "#636EFA", "⚠️ At Risk": "#EF553B"},
        template="plotly_dark",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- SEGMENT TABS ---
    st.write("### 🔎 Detailed Segment Breakdown")
    tab1, tab2, tab3 = st.tabs(["💎 VIPs", "⚠️ At Risk", "📂 All Guests"])

    with tab1:
        vips = df[df['Segment'] == "💎 VIP"].sort_values("completed", ascending=False)
        if not vips.empty:
            st.dataframe(vips[['name', 'phone', 'total_bookings', 'completed', 'last_seen']], use_container_width=True)
        else:
            st.write("No VIPs identified yet. Keep providing great service!")

    with tab2:
        risky = df[df['Segment'] == "⚠️ At Risk"].sort_values("flakes", ascending=False)
        if not risky.empty:
            st.dataframe(risky[['name', 'phone', 'total_bookings', 'flakes', 'reliability', 'last_seen']], use_container_width=True)
            st.warning("Recommendation: Consider requiring deposits for these customers.")
        else:
            st.write("No high-risk customers found. Great job!")

    with tab3:
        st.dataframe(df.sort_values("total_bookings", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
