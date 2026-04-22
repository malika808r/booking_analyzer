import streamlit as st
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_conn, get_menu_data, toggle_item_availability

def main():
    st.set_page_config(page_title="Booking Analyzer | Menu", page_icon="🍽", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    rid = st.session_state.get("selected_restaurant_id")

    if not rid:
        st.warning("Please select a restaurant in the sidebar or on the Home page.")
        return

    st.title("🍽 Menu Management")
    st.caption("Inventory control for Booking Analyzer")
    st.markdown("---")

    conn = get_conn()
    df_menu = get_menu_data(conn, rid)
    conn.close()

    if df_menu.empty:
        st.info("This restaurant has no menu items yet.")
        return

    categories = df_menu["category"].unique()
    
    for cat in categories:
        st.subheader(cat)
        items = df_menu[df_menu["category"] == cat]
        
        for _, item in items.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1.5])
                with col1:
                    st.markdown(f"**{item['item']}**")
                    st.caption(item['description'])
                with col2:
                    st.write(f"{item['price']} {item['currency']}")
                
                with col3:
                    label = "Disable" if item['is_available'] else "Enable"
                    btn_type = "secondary" if item['is_available'] else "primary"
                    
                    if st.button(label, key=f"toggle_{item['id']}", use_container_width=True):
                        try:
                            # Re-open connection for the action if needed, or use existing if it's open
                            conn_action = get_conn()
                            new_state = toggle_item_availability(conn_action, item['id'], item['is_available'])
                            conn_action.close()
                            st.success(f"Status updated: {'Available' if new_state else 'Out of stock'}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Action failed: {e}")

                    if item['is_available']:
                        st.success("Available")
                    else:
                        st.error("Out of stock")

if __name__ == "__main__":
    main()
