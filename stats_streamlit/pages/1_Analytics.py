import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_kpis, get_dynamics, get_statuses, get_heatmap_data, get_detailed_bookings_report
import plotly.express as px
import plotly.graph_objects as go
import io

def main():
    st.set_page_config(page_title="Booking Analyzer | Analytics", page_icon="📊", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    
    # --- REFRESH CACHE BUTTON ---
    with st.sidebar:
        st.divider()
        if st.button("🔄 Refresh Data", use_container_width=True, help="Clears the local cache and fetches the latest data from the database."):
            st.cache_data.clear()
            st.rerun()

    rid = st.session_state.get("selected_restaurant_id")

    if not rid:
        st.warning("Please select a restaurant in the sidebar or on the Home page.")
        return

    st.title("📊 Analytics Dashboard")
    st.caption("Strategic insights for Booking Analyzer")
    st.markdown("---")

    # --- KPI ROW ---
    kpis = get_kpis(rid)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Bookings Today", kpis["today_bookings"], delta="Live")
    with c2:
        st.metric("Free Tables", kpis["free_tables"], delta="-2", delta_color="inverse")
    with c3:
        st.metric("Cancellation Rate", f"{kpis['cancel_rate']}%", delta="-0.5%", delta_color="normal")
    with c4:
        st.metric("Avg. Party Size", f"{kpis['avg_party_size']}", delta="+0.2")

    st.markdown("### 📈 Performance Trends")
    
    # --- FILTERS ---
    with st.expander("Filter Data Range", expanded=False):
        colA, colB, colC = st.columns([2, 2, 1])
        with colA:
            d_from = st.date_input("From", value=date.today() - timedelta(days=30))
        with colB:
            d_to = st.date_input("To", value=date.today())
        with colC:
            group_by = st.selectbox("Group By", options=["Day", "Week", "Month"], index=0)

    from_ts = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    to_ts = datetime(d_to.year, d_to.month, d_to.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    # --- CHARTS ---
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.write("**Booking Dynamics**")
        df_summary = get_dynamics(rid, from_ts, to_ts, group_by)
        if not df_summary.empty:
            df_summary["bucket"] = pd.to_datetime(df_summary["bucket"])
            fig_dyn = px.area(df_summary, x="bucket", y="bookings", 
                              color_discrete_sequence=["#FFD700"],
                              template="plotly_dark")
            fig_dyn.update_traces(
                hovertemplate="<b>Date:</b> %{x}<br><b>Bookings:</b> %{y}<extra></extra>",
                fillcolor='rgba(255, 215, 0, 0.2)',
                line=dict(width=3, color='#FFD700')
            )
            fig_dyn.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), 
                height=300,
                hovermode="x unified",
                xaxis_title="",
                yaxis_title="Total Bookings",
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_dyn, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No bookings found for selected period.")

    with col_right:
        st.write("**Status Distribution**")
        df_status = get_statuses(rid, from_ts, to_ts)
        if not df_status.empty:
            fig_pie = px.pie(df_status, values="cnt", names="status", 
                             hole=0.4,
                             color_discrete_sequence=["#FFD700", "#FFC107", "#FFB300", "#FFA000"],
                             template="plotly_dark")
            fig_pie.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No status data.")

    st.markdown("### 🕒 Peak Hours - Heatmap Analysis")
    st.markdown("Optimize your staffing and energy costs by identifying slow and high-traffic periods.")
    
    df_heat = get_heatmap_data(rid)
    if not df_heat.empty:
        # Pivot the data for the heatmap
        days_map = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
        df_heat["day_name"] = df_heat["dow"].map(days_map)
        
        pivot_heat = df_heat.pivot(index="day_name", columns="hour", values="bookings").fillna(0)
        
        # --- HIDE EMPTY HOURS ---
        pivot_heat = pivot_heat.loc[:, (pivot_heat != 0).any(axis=0)]
        
        # Ensure correct day order
        ordered_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        pivot_heat = pivot_heat.reindex(ordered_days)
        
        def format_hour(h):
            h = int(float(h))
            if h == 0: return "12 AM"
            if h < 12: return f"{h} AM"
            if h == 12: return "12 PM"
            return f"{h-12} PM"

        fig_heat = px.imshow(pivot_heat, 
                             labels=dict(x="Time of Day", y="Day", color="Bookings"),
                             x=[format_hour(h) for h in pivot_heat.columns],
                             y=pivot_heat.index,
                             color_continuous_scale="YlOrRd", # Classic heat scale
                             aspect="auto",
                             template="plotly_dark")
        
        fig_heat.update_traces(
            hovertemplate="<b>%{y} at %{x}</b><br>Total Bookings: %{z}<extra></extra>"
        )
        
        fig_heat.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), 
            height=350,
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_heat, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("No data available for heatmap.")

    st.divider()
    
    # --- EXPORT SECTION ---
    st.markdown("### 📥 Report Export & Downloads")
    st.write("Generate professional reports for bookkeeping or internal presentations.")
    
    df_report = get_detailed_bookings_report(rid, from_ts, to_ts)
    
    if not df_report.empty:
        # Pre-calculate filename
        report_tag = d_from.strftime("%Y-%m") if d_from.month == d_to.month else f"{d_from.strftime('%Y%m')}_{d_to.strftime('%Y%m')}"
        filename_prefix = f"Booking_Report_{report_tag}"
        
        ex_col1, ex_col2, _ = st.columns([1, 1, 2])
        
        with ex_col1:
            csv = df_report.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{filename_prefix}.csv",
                mime='text/csv',
                use_container_width=True,
            )
            
        with ex_col2:
            buffer = io.BytesIO()
            # Excel doesn't support timezones, so we must remove them
            df_excel = df_report.copy()
            if "Date & Time" in df_excel.columns:
                df_excel["Date & Time"] = pd.to_datetime(df_excel["Date & Time"]).dt.tz_localize(None)
                
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='Bookings')
            
            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name=f"{filename_prefix}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True,
            )
            
        st.info(f"Total entries in report: {len(df_report)}")
        st.write("**Data Preview (Raw Entries)**")
        st.dataframe(df_report, use_container_width=True)
    else:
        st.warning("No data matches selected filters for export.")

if __name__ == "__main__":
    main()
