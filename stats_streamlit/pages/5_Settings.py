import streamlit as st
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_conn, update_restaurant_info, get_restaurant_tables, add_restaurant_table, delete_restaurant_table
import pandas as pd

def main():
    st.set_page_config(page_title="Booking Analyzer | Settings", page_icon="⚙️", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    rid = st.session_state.get("selected_restaurant_id")

    st.title("⚙️ Business Settings")
    st.caption("Customize your Booking Analyzer experience")
    st.markdown("---")

    if not rid:
        st.warning("Please select a restaurant to view its settings.")
        return

    conn = get_conn()
    
    # Fetch Restaurant Info
    df_res = pd.read_sql("SELECT name, description, address, phone FROM restaurants WHERE id = %s", conn, params=[rid])
    
    if not df_res.empty:
        res = df_res.iloc[0]
        
        st.subheader("Restaurant Profile")
        with st.form("settings_form"):
            name = st.text_input("Restaurant Name", value=res['name'])
            addr = st.text_input("Address", value=res['address'])
            phone = st.text_input("Phone", value=res['phone'])
            desc = st.text_area("Description", value=res['description'])
            
            if st.form_submit_button("Save Changes"):
                try:
                    update_restaurant_info(conn, rid, name, addr, phone, desc)
                    st.success("Configuration updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update: {e}")

    st.divider()
    
    # --- TABLES MANAGEMENT ---
    st.subheader("🪑 Tables & Capacity Management")
    st.write("Manage your restaurant's physical layout and table limits.")
    
    # 1. Add Table Form
    with st.expander("➕ Add New Table", expanded=False):
        with st.form("add_table_form"):
            t_label = st.text_input("Table Label", placeholder="e.g. Table 1, VIP Booth")
            t_capacity = st.number_input("Guest Capacity", min_value=1, max_value=20, value=4)
            if st.form_submit_button("Add Table", use_container_width=True):
                if t_label:
                    try:
                        add_restaurant_table(rid, t_label, t_capacity)
                        st.success(f"Added {t_label} successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Enter a label.")

    # 2. List & Delete Tables
    df_tables = get_restaurant_tables(rid)
    if not df_tables.empty:
        for _, table in df_tables.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{table['label']}**")
                c2.write(f"Capacity: {table['capacity']} guests")
                if c3.button("🗑", key=f"del_t_{table['id']}", use_container_width=True):
                    try:
                        delete_restaurant_table(table['id'])
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
    else:
        st.info("No tables configured. Use the form above to add your first table.")

    st.divider()
    st.subheader("Account Information")
    st.write(f"**Email:** {user.email or 'N/A'}")
    st.write(f"**Phone:** {user.phone or 'N/A'}")
    st.write(f"**Security Role:** {user.role}")
    
    if st.button("Change Password"):
        st.info("Password reset link sent to your email.")

    conn.close()

if __name__ == "__main__":
    main()
