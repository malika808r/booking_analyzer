import os
import time
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st
from passlib.hash import bcrypt

# --- CONFIG ---
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def wait_for_db(conn_func, max_retries=30, delay=2):
    """Retries database connection until successful or max_retries reached."""
    for i in range(max_retries):
        try:
            conn = conn_func()
            conn.close()
            return True
        except Exception:
            time.sleep(delay)
    return False

def get_trunc_value(group_by: str) -> str:
    trunc_map = {"Day": "day", "Week": "week", "Month": "month"}
    return trunc_map.get(group_by, "day")

@st.cache_data(ttl=60)
def get_kpis(restaurant_id):
    """Returns essential KPIs for the dashboard. Cached for 1 min."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Bookings Today
            cur.execute("""
                SELECT count(*) as count 
                FROM bookings 
                WHERE restaurant_id = %s AND start_time::date = current_date
            """, (restaurant_id,))
            today_bookings = cur.fetchone()["count"]

            # 2. Total Tables
            cur.execute("SELECT count(*) as count FROM restaurant_tables WHERE restaurant_id = %s", (restaurant_id,))
            total_tables = cur.fetchone()["count"]

            # 3. Active Bookings Now
            cur.execute("""
                SELECT count(DISTINCT table_id) as count 
                FROM bookings 
                WHERE restaurant_id = %s 
                  AND status IN ('BOOKED', 'COMPLETED') 
                  AND current_timestamp BETWEEN start_time AND end_time
            """, (restaurant_id,))
            occupied_tables = cur.fetchone()["count"]
            free_tables = max(0, total_tables - occupied_tables)

            # 4. Cancellation Rate
            cur.execute("""
                SELECT 
                    count(*) FILTER (WHERE status = 'CANCELLED' OR status = 'NO_SHOW') as cancelled,
                    count(*) as total,
                    avg(party_size) as avg_party
                FROM bookings 
                WHERE restaurant_id = %s
            """, (restaurant_id,))
            res = cur.fetchone()
            cancel_rate = (res["cancelled"] / res["total"] * 100) if res["total"] > 0 else 0
            avg_party = res["avg_party"] or 0

            return {
                "today_bookings": today_bookings,
                "free_tables": free_tables,
                "cancel_rate": round(cancel_rate, 1),
                "avg_party_size": round(float(avg_party), 1)
            }
    finally:
        conn.close()

@st.cache_data(ttl=300)
def get_dynamics(restaurant_id, from_ts, to_ts, group_by):
    conn = get_conn()
    try:
        trunc = get_trunc_value(group_by)
        sql = f"""
            SELECT 
                date_trunc('{trunc}', start_time) as bucket,
                count(*) as bookings
            FROM bookings
            WHERE restaurant_id = %s AND start_time >= %s AND start_time <= %s
            GROUP BY 1 ORDER BY 1 ASC
        """
        return pd.read_sql(sql, conn, params=[restaurant_id, from_ts, to_ts])
    finally:
        conn.close()

@st.cache_data(ttl=300)
def get_statuses(restaurant_id, from_ts, to_ts):
    conn = get_conn()
    try:
        sql = """
            SELECT status, count(*) as cnt
            FROM bookings
            WHERE restaurant_id = %s AND start_time >= %s AND start_time <= %s
            GROUP BY status ORDER BY cnt DESC
        """
        return pd.read_sql(sql, conn, params=[restaurant_id, from_ts, to_ts])
    finally:
        conn.close()

def get_menu_data(conn, restaurant_id):
    # Not caching menu yet as it might change frequently by owner
    sql = """
        SELECT i.id, c.name as category, i.name as item, i.description, i.price, i.currency, i.is_available
        FROM menu_categories c
        JOIN menu_items i ON i.category_id = c.id
        WHERE c.restaurant_id = %s
        ORDER BY c.sort_order, i.sort_order
    """
    return pd.read_sql(sql, conn, params=[restaurant_id])

def update_restaurant_info(conn, rid, name, address, phone, description, user_email="System"):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE restaurants 
            SET name = %s, address = %s, phone = %s, description = %s, updated_at = now()
            WHERE id = %s
        """, (name, address, phone, description, rid))
        log_action(rid, user_email, "UPDATE_PROFILE", f"Updated restaurant info: {name}")
    conn.commit()

def toggle_item_availability(conn, item_id, current_state, rid=None, user_email="System"):
    new_state = not current_state
    with conn.cursor() as cur:
        cur.execute("UPDATE menu_items SET is_available = %s, updated_at = now() WHERE id = %s", (new_state, item_id))
        if rid:
            cur.execute("SELECT name FROM menu_items WHERE id = %s", (item_id,))
            name = cur.fetchone()[0] if cur.rowcount > 0 else "Unknown"
            log_action(rid, user_email, "TOGGLE_AVAILABILITY", f"Set {name} to {'Available' if new_state else 'Unavailable'}")
    conn.commit()
    return new_state

@st.cache_data(ttl=300)
def get_heatmap_data(restaurant_id):
    conn = get_conn()
    try:
        sql = """
            SELECT 
                extract(dow from start_time) as dow,
                extract(hour from start_time) as hour,
                count(*) as bookings
            FROM bookings
            WHERE restaurant_id = %s
            GROUP BY 1, 2
            ORDER BY 1, 2
        """
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

@st.cache_data(ttl=300)
def get_detailed_bookings_report(restaurant_id, from_ts, to_ts):
    conn = get_conn()
    try:
        sql = """
            SELECT 
                b.start_time as "Date & Time",
                b.customer_name as "Customer",
                b.customer_phone as "Phone",
                b.party_size as "Guests",
                t.label as "Table",
                b.status as "Status"
            FROM bookings b
            JOIN restaurant_tables t ON b.table_id = t.id
            WHERE b.restaurant_id = %s AND b.start_time >= %s AND b.start_time <= %s
            ORDER BY b.start_time ASC
        """
        return pd.read_sql(sql, conn, params=[restaurant_id, from_ts, to_ts])
    finally:
        conn.close()

def get_latest_bookings(restaurant_id, limit=20):
    conn = get_conn()
    try:
        sql = """
            SELECT 
                created_at,
                customer_name,
                party_size,
                start_time,
                status
            FROM bookings
            WHERE restaurant_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return pd.read_sql(sql, conn, params=[restaurant_id, limit])
    finally:
        conn.close()

# --- NEW CRUD OPERATIONS ---

def get_menu_categories(restaurant_id):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM menu_categories WHERE restaurant_id = %s ORDER BY sort_order", (restaurant_id,))
            return cur.fetchall()
    finally:
        conn.close()

def add_menu_item(category_id, name, description, price, currency="USD", rid=None, user_email="System"):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (id, category_id, name, description, price, currency, is_available, sort_order)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, true, 0)
            """, (category_id, name, description, price, currency))
            if rid:
                log_action(rid, user_email, "ADD_MENU_ITEM", f"Added dish: {name} ({price} {currency})")
        conn.commit()
    finally:
        conn.close()

def delete_menu_item(item_id, rid=None, user_email="System"):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if rid:
                cur.execute("SELECT name FROM menu_items WHERE id = %s", (item_id,))
                name = cur.fetchone()[0] if cur.rowcount > 0 else "Unknown"
                log_action(rid, user_email, "DELETE_MENU_ITEM", f"Deleted dish: {name}")
            cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        conn.commit()
    finally:
        conn.close()

def get_restaurant_tables(restaurant_id):
    conn = get_conn()
    try:
        sql = "SELECT id, label, capacity FROM restaurant_tables WHERE restaurant_id = %s ORDER BY label"
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

def add_restaurant_table(restaurant_id, label, capacity, user_email="System"):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO restaurant_tables (id, restaurant_id, label, capacity)
                VALUES (gen_random_uuid(), %s, %s, %s)
            """, (restaurant_id, label, capacity))
            log_action(restaurant_id, user_email, "ADD_TABLE", f"Added table {label} (cap: {capacity})")
        conn.commit()
    finally:
        conn.close()

def delete_restaurant_table(table_id, rid=None, user_email="System"):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if rid:
                cur.execute("SELECT label FROM restaurant_tables WHERE id = %s", (table_id,))
                label = cur.fetchone()[0] if cur.rowcount > 0 else "Unknown"
                log_action(rid, user_email, "DELETE_TABLE", f"Deleted table: {label}")
            cur.execute("DELETE FROM restaurant_tables WHERE id = %s", (table_id,))
        conn.commit()
    finally:
        conn.close()

# --- SMART ANALYTICS & ML DATA ---

@st.cache_data(ttl=600)
def get_forecasting_data(restaurant_id):
    conn = get_conn()
    try:
        sql = """
            SELECT date_trunc('day', start_time)::date as date, count(*) as count 
            FROM bookings 
            WHERE restaurant_id = %s 
            GROUP BY 1 
            ORDER BY 1 ASC
        """
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

@st.cache_data(ttl=300)
def get_customer_metrics(restaurant_id):
    conn = get_conn()
    try:
        sql = """
            SELECT 
                COALESCE(customer_name, 'Unknown') as name,
                COALESCE(customer_phone, 'N/A') as phone,
                count(*) as total_bookings,
                count(*) FILTER (WHERE status = 'COMPLETED') as completed,
                count(*) FILTER (WHERE status IN ('CANCELLED', 'NO_SHOW')) as flakes,
                max(start_time) as last_seen
            FROM bookings
            WHERE restaurant_id = %s
            GROUP BY 1, 2
            ORDER BY total_bookings DESC
        """
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

# --- AUDIT LOGGING ---

def log_action(restaurant_id, user_email, action, details):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs (id, restaurant_id, user_email, action, details)
                VALUES (gen_random_uuid(), %s, %s, %s, %s)
            """, (restaurant_id, user_email, action, details))
        conn.commit()
    finally:
        conn.close()

def get_audit_logs(restaurant_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Safety check: Ensure the table exists even if bootstrap was skipped
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY,
                    restaurant_id UUID REFERENCES restaurants(id) ON DELETE SET NULL,
                    user_email VARCHAR(255),
                    action VARCHAR(128) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()
        
        sql = """
            SELECT created_at as "Time", user_email as "User", action as "Action", details as "Details"
            FROM audit_logs
            WHERE restaurant_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

# --- STAFF MANAGEMENT ---

def get_restaurant_staff(restaurant_id):
    conn = get_conn()
    try:
        sql = """
            SELECT u.id, u.email, u.role, u.created_at
            FROM users u
            JOIN restaurant_owners ro ON ro.owner_user_id = u.id
            WHERE ro.restaurant_id = %s
        """
        return pd.read_sql(sql, conn, params=[restaurant_id])
    finally:
        conn.close()

def add_staff_member(restaurant_id, email, password_plain, role="MODERATOR", admin_email="System"):
    conn = get_conn()
    try:
        pw_hash = bcrypt.hash(password_plain)
        with conn.cursor() as cur:
            # 1. Create User (or get if exists)
            cur.execute("SELECT id FROM users WHERE lower(email) = lower(%s)", (email,))
            row = cur.fetchone()
            if row:
                uid = row[0]
            else:
                cur.execute("""
                    INSERT INTO users (id, role, email, password_hash)
                    VALUES (gen_random_uuid(), %s, %s, %s)
                    RETURNING id
                """, (role, email, pw_hash))
                uid = cur.fetchone()[0]
            
            # 2. Link to Restaurant
            cur.execute("""
                INSERT INTO restaurant_owners (restaurant_id, owner_user_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (restaurant_id, uid))
            
            log_action(restaurant_id, admin_email, "ADD_STAFF", f"Added {role}: {email}")
        conn.commit()
    finally:
        conn.close()

def remove_staff_member(restaurant_id, user_id, email="Unknown", admin_email="System"):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM restaurant_owners WHERE restaurant_id = %s AND owner_user_id = %s", (restaurant_id, user_id))
            log_action(restaurant_id, admin_email, "REMOVE_STAFF", f"Removed access for user: {email}")
        conn.commit()
    finally:
        conn.close()

# --- BOT HELPERS ---

def link_telegram_to_user(user_id, tg_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET telegram_id = %s WHERE id = %s", (tg_id, user_id))
        conn.commit()
    finally:
        conn.close()

def get_restaurant_owners_tg(restaurant_id):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT u.telegram_id
                FROM users u
                JOIN restaurant_owners ro ON ro.owner_user_id = u.id
                WHERE ro.restaurant_id = %s AND u.telegram_id IS NOT NULL
            """
            cur.execute(sql, (restaurant_id,))
            return [r['telegram_id'] for r in cur.fetchall()]
    finally:
        conn.close()
