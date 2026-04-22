import streamlit as st
from ui_utils import require_login, render_sidebar, inject_custom_css
from stats_sql import get_restaurant_staff, add_staff_member, remove_staff_member

def main():
    st.set_page_config(page_title="Booking Analyzer | Staff", page_icon="👔", layout="wide")
    inject_custom_css()
    user = require_login()
    render_sidebar(user)
    
    if user.role != "OWNER":
        st.error("🚫 Access Denied. Only restaurant owners can manage staff.")
        st.stop()

    rid = st.session_state.get("selected_restaurant_id")
    if not rid:
        st.warning("Please select a restaurant to manage staff.")
        return

    st.title("👔 Staff Management")
    st.caption("Manage team access and moderator permissions")
    st.markdown("---")

    # --- ADD STAFF FORM ---
    with st.expander("👤 Add New Staff Member"):
        with st.form("add_staff_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            email = col1.text_input("Email Address")
            password = col2.text_input("Initial Password", type="password")
            
            role = st.selectbox("Assign Role", ["MODERATOR", "OWNER"], help="Moderators can manage bookings but not staff.")
            
            submit = st.form_submit_button("Create Account & Link", use_container_width=True)
            
            if submit:
                if email and password:
                    try:
                        add_staff_member(rid, email, password, role=role, admin_email=user.email)
                        st.success(f"Staff member {email} added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding staff: {e}")
                else:
                    st.error("Please provide both email and password.")

    # --- STAFF LIST ---
    df_staff = get_restaurant_staff(rid)
    
    if df_staff.empty:
        st.info("No staff members linked. You can add them using the form above.")
    else:
        st.write(f"### Current Team ({len(df_staff)} members)")
        
        # Display staff in a clean table-like view
        for _, row in df_staff.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                c1.markdown(f"**{row['email']}**")
                c2.caption(f"Role: {row['role']}")
                c3.caption(f"Created: {row['created_at'].strftime('%Y-%m-%d')}")
                
                # Prevent owner from deleting themselves (self-lockout)
                if row['email'].lower() != user.email.lower():
                    if c4.button("🗑️ Revoke", key=f"rev_{row['id']}", help="Remove restaurant access"):
                        remove_staff_member(rid, row['id'], email=row['email'], admin_email=user.email)
                        st.success(f"Revoked access for {row['email']}")
                        st.rerun()
                else:
                    c4.write("✅ (You)")

if __name__ == "__main__":
    main()
