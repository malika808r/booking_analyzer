import os
import time
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

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

def update_restaurant_info(conn, rid, name, address, phone, description):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE restaurants 
            SET name = %s, address = %s, phone = %s, description = %s, updated_at = now()
            WHERE id = %s
        """, (name, address, phone, description, rid))
    conn.commit()

def toggle_item_availability(conn, item_id, current_state):
    new_state = not current_state
    with conn.cursor() as cur:
        cur.execute("UPDATE menu_items SET is_available = %s, updated_at = now() WHERE id = %s", (new_state, item_id))
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
