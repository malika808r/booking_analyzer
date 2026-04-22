import streamlit as st
import pandas as pd
import psycopg2.extras
from dataclasses import dataclass
from passlib.hash import bcrypt
from stats_sql import get_conn

@dataclass
class SessionUser:
    id: str
    role: str
    email: str | None
    phone: str | None

def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Outfit:wght@300;600;900&display=swap');
    
    .main {
        background-color: #0E1117;
    }
    
    div[data-testid="stMetricValue"] {
        font-family: 'Outfit', sans-serif;
        font-weight: 900;
        color: #FFD700;
    }
    
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
    }
    
    p, span, div {
        font-family: 'Inter', sans-serif;
    }

    button[kind="primary"] {
        background-color: #FFD700;
        color: black;
        border: none;
    }
    
    div[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    .stButton>button {
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 215, 0, 0.2);
    }
    </style>
    """, unsafe_allow_html=True)

def find_user_by_identifier(conn, identifier: str):
    ident = identifier.strip()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("select * from users where email=%s or phone=%s limit 1", (ident, ident))
        return cur.fetchone()

def require_login():
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        # Login Screen Aesthetic
        st.markdown("<h1 style='text-align: center;'>Booking Analyzer 🚀</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Advanced Reservation Analytics & Guest Insights</p>", unsafe_allow_html=True)
        
        col_l, col_m, col_r = st.columns([1, 1, 1])
        with col_m:
            with st.container(border=True):
                st.subheader("Access Analytics Dashboard")
                identifier = st.text_input("Email / Phone", placeholder="mod@example.com")
                password = st.text_input("Password", type="password")
                
                if st.button("Login", use_container_width=True, type="primary"):
                    if identifier == "admin" and password == "123":
                        # Demo access - fetch real role from DB
                        try:
                            conn = get_conn()
                            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                                cur.execute("SELECT * FROM users WHERE role IN ('ADMIN', 'MODERATOR', 'ROLE_ADMIN') LIMIT 1")
                                row = cur.fetchone()
                            conn.close()
                            if row:
                                st.session_state.user = SessionUser(
                                    id=str(row["id"]),
                                    role=row.get("role"),
                                    email=row.get("email"),
                                    phone=row.get("phone")
                                )
                                st.rerun()
                            else:
                                st.error("No administrative users found in database.")
                        except Exception as e:
                            st.error(f"Demo lookup failed: {e}")
                        st.stop()
                    
                    try:
                        conn = get_conn()
                        row = find_user_by_identifier(conn, identifier)
                        conn.close()
                        if row:
                            # Verify bcrypt hash
                            hash_ = row.get("password_hash") or ""
                            if hash_.startswith("{bcrypt}"): hash_ = hash_.replace("{bcrypt}", "")
                            if bcrypt.verify(password, hash_):
                                st.session_state.user = SessionUser(
                                    id=str(row["id"]),
                                    role=row.get("role"),
                                    email=row.get("email"),
                                    phone=row.get("phone")
                                )
                                st.rerun()
                            else:
                                st.error("Invalid password")
                        else:
                            st.error("User not found")
                    except Exception as e:
                        st.error(f"DB Error: {e}")
        
        st.info("💡 Hint: Use 'admin' and '123' for demo access.")
        st.stop()
    
    return st.session_state.user

def load_restaurants(conn, user: SessionUser) -> pd.DataFrame:
    if user.role in ["MODERATOR", "ADMIN", "ROLE_ADMIN"]:
        q = "select id, name from restaurants order by name asc"
        return pd.read_sql(q, conn)
    q = """
        select r.id, r.name from restaurants r
        join restaurant_owners ro on ro.restaurant_id = r.id
        where ro.owner_user_id = %s order by r.name asc
    """
    return pd.read_sql(q, conn, params=[user.id])

def render_sidebar(user: SessionUser):
    with st.sidebar:
        st.title("Analyzer")
        st.write(f"Logged as: **{user.role}**")
        
        try:
            conn = get_conn()
            restaurants = load_restaurants(conn, user)
            conn.close()
            
            if not restaurants.empty:
                st.divider()
                st.selectbox(
                    "Active Restaurant",
                    options=list(restaurants["id"]),
                    format_func=lambda x: restaurants.loc[restaurants["id"] == x, "name"].iloc[0],
                    key="selected_restaurant_id"
                )
        except Exception as e:
            st.sidebar.error(f"Error loading restaurants: {e}")

        st.divider()
        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()
