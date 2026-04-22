import os
from datetime import date, datetime, timedelta, timezone
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
        cur.execute("select * from users where email=%s or phone=%s limit 1", (ident, ident))
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
    identifier = st.text_input("Email или Телефон", placeholder="mod@example.com")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти"):
        if not identifier.strip() or not password:
            st.error("Введите логин и пароль.")
            st.stop()

        if identifier.strip() == "admin" and password == "123":
            st.session_state.user = SessionUser(id="1", role="MODERATOR", email="admin", phone=None)
            st.rerun()

        try:
            conn = get_conn()
            row = find_user_by_identifier(conn, identifier)
            conn.close()
        except Exception as e:
            st.error(f"Ошибка подключения к БД: {e}")
            st.stop()

        if not row:
            st.error("Пользователь не найден.")
            st.stop()

        role = row.get("role")
        if role not in ALLOWED_ROLES:
            st.error(f"Доступ запрещен. Роль: {role}")
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

    st.info("💡 Используйте mod@example.com и пароль mod123456")
    return None

def load_restaurants_for_user(conn, user: SessionUser) -> pd.DataFrame:
    if user.role in ["MODERATOR", "ADMIN", "ROLE_ADMIN"]:
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

# --- ГРАФИКИ ---
def q_summary(conn, restaurant_id: str, from_ts: str, to_ts: str, group_by: str) -> pd.DataFrame:
    trunc = get_trunc_value(group_by)
    sql = f"""
        select
          date_trunc('{trunc}', start_time) as bucket,
          count(*) as bookings
        from bookings
        where restaurant_id = %s
          and start_time >= %s
          and start_time <= %s
        group by 1
        order by 1 asc
    """
    return pd.read_sql(sql, conn, params=[restaurant_id, from_ts, to_ts])

def q_statuses(conn, restaurant_id: str, from_ts: str, to_ts: str) -> pd.DataFrame:
    sql = """
        select status, count(*) as cnt
        from bookings
        where restaurant_id = %s
          and start_time >= %s
          and start_time <= %s
        group by status
        order by cnt desc
    """
    return pd.read_sql(sql, conn, params=[restaurant_id, from_ts, to_ts])

def main():
    user = require_login()
    if user is None:
        return

    st.divider()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        st.success("🟢 База данных: Подключено и работает", icon="✅")
    except Exception as e:
        st.error(f"🔴 Ошибка БД: {e}", icon="🚨")
        return
    # --- КОНЕЦ НОВОГО БЛОКА ---

    try:
        conn = get_conn()
        restaurants = load_restaurants_for_user(conn, user)
    except Exception as e:
        st.error(f"Не удалось загрузить список ресторанов: {e}")
        return

    if restaurants.empty:
        st.warning("К вам не привязан ни один ресторан.")
        conn.close()
        return

    colA, colB, colC = st.columns([2, 2, 1])
    with colA:
        rid = st.selectbox(
            "Выберите ресторан:",
            options=list(restaurants["id"]),
            format_func=lambda x: restaurants.loc[restaurants["id"] == x, "name"].iloc[0],
        )
    with colB:
        default_from = date.today() - timedelta(days=30)
        default_to = date.today()
        d_from = st.date_input("С (дата)", value=default_from)
        d_to = st.date_input("По (дата)", value=default_to)
    with colC:
        group_by = st.selectbox("Группировка", options=["День", "Неделя", "Месяц"], index=0)

    from_ts = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    to_ts = datetime(d_to.year, d_to.month, d_to.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    st.divider()

    st.subheader("Динамика бронирований")
    df_summary = q_summary(conn, rid, from_ts, to_ts, group_by)
    if df_summary.empty:
        st.info("Нет бронирований за этот период.")
    else:
        df_summary["bucket"] = pd.to_datetime(df_summary["bucket"])
        df_plot = df_summary.set_index("bucket")[["bookings"]]
        st.line_chart(df_plot)
        st.dataframe(df_summary, use_container_width=True)

    st.divider()

    st.subheader("Статусы бронирований")
    df_status = q_statuses(conn, rid, from_ts, to_ts)
    if df_status.empty:
        st.info("Нет данных по статусам.")
    else:
        st.bar_chart(df_status.set_index("status")[["cnt"]])

    conn.close()

if __name__ == "__main__":
    main()