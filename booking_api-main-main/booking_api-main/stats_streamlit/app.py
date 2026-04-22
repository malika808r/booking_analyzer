import os
from dataclasses import dataclass
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st
from passlib.hash import bcrypt

from stats_sql import get_trunc_value


st.set_page_config(page_title="Статистика ресторанов", layout="wide")


DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")

ALLOWED_ROLES = {"OWNER", "MODERATOR", "ROLE_OWNER", "ROLE_MODERATOR", "ADMIN", "ROLE_ADMIN"}

@dataclass
class SessionUser:
    id: str
    role: str
    email: str | None
    phone: str | None


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def find_user_by_identifier(conn, identifier: str):
    ident = identifier.strip()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        
        cur.execute("select * from users where username=%s limit 1", (ident,))
        return cur.fetchone()

def require_login():
    if "user" not in st.session_state:
        st.session_state.user = None

    st.title("Аналитика Ресторанов 📊")

    
    if st.session_state.user is not None:
        u: SessionUser = st.session_state.user
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"✅ Вы вошли как {u.role} — {u.email or u.phone or u.id}")
        with col2:
            if st.button("Выйти (Logout)"):
                st.session_state.user = None
                st.rerun()
        return u

    
    st.subheader("Вход в систему")
    identifier = st.text_input("Логин", placeholder="admin")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти"):
        if not identifier.strip() or not password:
            st.error("Введите логин и пароль.")
            st.stop()

        
        if identifier.strip() == "admin" and password == "123":
            st.session_state.user = SessionUser(id="1", role="MODERATOR", email="admin", phone=None)
            st.rerun()
        

        st.error("Используйте логин admin и пароль 123 для входа.")
        st.stop()

    return None
    
    st.subheader("Вход в систему")
    identifier = st.text_input("Email или Телефон", placeholder="owner@example.com")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти"):
        if not identifier.strip() or not password:
            st.error("Введите логин и пароль.")
            st.stop()

        try:
            conn = get_conn()
            row = find_user_by_identifier(conn, identifier)
            conn.close()
        except Exception as e:
            st.error(f"Ошибка подключения к базе данных: {e}")
            st.stop()

        if not row:
            st.error("Пользователь не найден.")
            st.stop()

        role = row.get("role")
        
        if role not in {"OWNER", "MODERATOR", "ROLE_OWNER", "ROLE_MODERATOR", "ADMIN", "ROLE_ADMIN"}:
            st.error(f"Доступ запрещен. Ваша текущая роль в базе: {role}")
            st.stop()

        
        hash_ = row.get("password_hash") or row.get("password") or ""

        
        if hash_.startswith("{bcrypt}"):
            hash_ = hash_.replace("{bcrypt}", "")

        try:
            ok = bcrypt.verify(password, hash_)
        except Exception:
            ok = False

        if not ok:
            st.error("Неверный пароль.")
            st.stop()

        if not row.get("is_active", True):
            st.error("Аккаунт заблокирован или неактивен.")
            st.stop()

        
        st.session_state.user = SessionUser(
            id=str(row["id"]),
            role=role,
            email=row.get("email"),
            phone=row.get("phone"),
        )
        st.rerun()

    st.info("💡 Используйте данные от вашего аккаунта владельца.")
    return None


def load_restaurants_for_user(conn, user: SessionUser) -> pd.DataFrame:
    
    if user.role == "MODERATOR":
        q = "select id, name from restaurants order by name asc"
        return pd.read_sql(q, conn)

    
    q = """
        select r.id, r.name
        from restaurants r
        join restaurant_owners ro on ro.restaurant_id = r.id
        where ro.owner_user_id = %s
        order by r.name asc
    """
    return pd.read_sql(q, conn, params=[user.id])
def render_metrics(conn, rid, d_from, d_to, group_by):
    trunc_val = get_trunc_value(group_by)


    
def main():
    user = require_login()
    if user is None:
        return

    st.divider()
    st.subheader("Выберите ресторан для просмотра статистики")

    try:
        conn = get_conn()
        restaurants = load_restaurants_for_user(conn, user)
    except Exception as e:
        st.error(f"Не удалось загрузить список ресторанов: {e}")
        return

    if restaurants.empty:
        st.warning("К вам не привязан ни один ресторан. Обратитесь к администратору.")
        conn.close()
        return

    
    rid = st.selectbox(
        "Ваши рестораны:",
        options=list(restaurants["id"]),
        format_func=lambda x: restaurants.loc[restaurants["id"] == x, "name"].iloc[0],
    )

    st.session_state.selected_restaurant_id = rid
    conn.close()

    st.info("Следующим шагом здесь появятся графики и метрики для выбранного ресторана! 📈")

if __name__ == "__main__":
    main()