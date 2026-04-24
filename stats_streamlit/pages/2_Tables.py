import streamlit as st
import pandas as pd
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_restaurant_tables, add_restaurant_table, delete_restaurant_table

def main():
    st.set_page_config(page_title="Booking Analyzer | Tables", page_icon=None, layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    rid = st.session_state.get("selected_restaurant_id")

    if not rid:
        st.warning("Please select a restaurant to manage tables.")
        return

    st.title("Table Management")
    st.caption("Inventory of restaurant tables and guest capacity")
    st.markdown("---")

    # --- ADD TABLE FORM ---
    with st.expander("Add New Table"):
        with st.form("add_table_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            label = col1.text_input("Table Label (e.g. T-10, VIP-1)")
            capacity = col2.number_input("Guest Capacity", min_value=1, max_value=20, value=4)
            submit = st.form_submit_button("Add Table", use_container_width=True)
            
            if submit:
                if label:
                    add_restaurant_table(rid, label, capacity, user_email=user.email)
                    st.success(f"Table {label} added successfully!")
                    st.rerun()
                else:
                    st.error("Please provide a label for the table.")

    # --- TABLE LIST ---
    df_tables = get_restaurant_tables(rid)
    
    if df_tables.empty:
        st.info("No tables defined yet. Add your first table above.")
    else:
        st.write(f"### Current Inventory ({len(df_tables)} tables)")
        
        # Display tables in a grid or table
        grid = st.columns(4)
        for i, row in df_tables.iterrows():
            with grid[i % 4]:
                with st.container(border=True):
                    st.markdown(f"**Table: {row['label']}**")
                    st.markdown(f"Capacity: {row['capacity']}")
                    if st.button("Delete", key=f"del_{row['id']}", use_container_width=True):
                        delete_restaurant_table(row['id'], rid=rid, user_email=user.email)
                        st.success(f"Deleted {row['label']}")
                        st.rerun()

if __name__ == "__main__":
    main()
