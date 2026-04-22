import os
import uuid
from datetime import datetime, timedelta, timezone
import psycopg2
import psycopg2.extras
from passlib.hash import bcrypt

def get_db_config():
    return {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "booking_db"),
        "user": os.getenv("DB_USER", "booking_user"),
        "password": os.getenv("DB_PASSWORD", "booking_password"),
    }

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  role VARCHAR(32) NOT NULL,
  email VARCHAR(255) UNIQUE,
  phone VARCHAR(64) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS restaurants (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  address TEXT,
  phone VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS restaurant_owners (
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (restaurant_id, owner_user_id)
);

CREATE TABLE IF NOT EXISTS restaurant_tables (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  label VARCHAR(128) NOT NULL,
  capacity INT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS menu_categories (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  sort_order INT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS menu_items (
  id UUID PRIMARY KEY,
  category_id UUID NOT NULL REFERENCES menu_categories(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  price NUMERIC(12,2) NOT NULL,
  currency VARCHAR(16),
  photo_url TEXT,
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bookings (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  table_id UUID NOT NULL REFERENCES restaurant_tables(id) ON DELETE CASCADE,
  party_size INT NOT NULL,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  status VARCHAR(32) NOT NULL,
  customer_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  customer_name VARCHAR(255),
  customer_phone VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

def upsert_user(cur, role, email, phone, password_plain):
    cur.execute("select id from users where lower(email)=lower(%s) limit 1", (email,))
    row = cur.fetchone()
    if row: return row["id"]
    uid = uuid.uuid4()
    pw_hash = bcrypt.hash(password_plain)
    cur.execute("insert into users(id, role, email, phone, password_hash, is_active) values (%s,%s,%s,%s,%s,true)",
                (str(uid), role, email, phone, pw_hash))
    return str(uid)

def upsert_restaurant(cur, name, description, address, phone):
    cur.execute("select id from restaurants where lower(name)=lower(%s) limit 1", (name,))
    row = cur.fetchone()
    if row: return row["id"]
    rid = uuid.uuid4()
    cur.execute("insert into restaurants(id, name, description, address, phone) values (%s,%s,%s,%s,%s)",
                (str(rid), name, description, address, phone))
    return str(rid)

def ensure_owner_link(cur, restaurant_id, owner_user_id):
    cur.execute("insert into restaurant_owners(restaurant_id, owner_user_id) values (%s,%s) on conflict do nothing",
                (restaurant_id, owner_user_id))

def ensure_table(cur, restaurant_id, label, capacity):
    cur.execute("select id from restaurant_tables where restaurant_id=%s and lower(label)=lower(%s) limit 1", (restaurant_id, label))
    row = cur.fetchone()
    if row: return row["id"]
    tid = uuid.uuid4()
    cur.execute("insert into restaurant_tables(id, restaurant_id, label, capacity, is_active) values (%s,%s,%s,%s,true)",
                (str(tid), restaurant_id, label, capacity))
    return str(tid)

def ensure_category(cur, restaurant_id, name, sort_order):
    cur.execute("select id from menu_categories where restaurant_id=%s and lower(name)=lower(%s) limit 1", (restaurant_id, name))
    row = cur.fetchone()
    if row: return row["id"]
    cid = uuid.uuid4()
    cur.execute("insert into menu_categories(id, restaurant_id, name, sort_order, is_active) values (%s,%s,%s,%s,true)",
                (str(cid), restaurant_id, name, sort_order))
    return str(cid)

def ensure_item(cur, category_id, name, description, price, currency, sort_order):
    cur.execute("select id from menu_items where category_id=%s and lower(name)=lower(%s) limit 1", (category_id, name))
    row = cur.fetchone()
    if row: return row["id"]
    iid = uuid.uuid4()
    cur.execute("insert into menu_items(id, category_id, name, description, price, currency, is_available, sort_order) values (%s,%s,%s,%s,%s,%s,true,%s)",
                (str(iid), category_id, name, description, price, currency, sort_order))
    return str(iid)

def run_bootstrap():
    config = get_db_config()
    conn = psycopg2.connect(**config)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Schema
            cur.execute(SCHEMA_SQL)
            
            # 2. Data
            mod_id = upsert_user(cur, "MODERATOR", "mod@example.com", None, "mod123456")
            owner1_id = upsert_user(cur, "OWNER", "owner1@example.com", None, "owner123456")
            cust_id = upsert_user(cur, "CUSTOMER", "cust1@example.com", None, "cust123456")

            r1 = upsert_restaurant(cur, "Demo Restaurant A", "Seed restaurant A", "Bishkek A", "+996000000001")
            r2 = upsert_restaurant(cur, "Demo Restaurant B", "Seed restaurant B", "Bishkek B", "+996000000002")

            ensure_owner_link(cur, r1, owner1_id)
            ensure_owner_link(cur, r2, owner1_id)

            t1 = ensure_table(cur, r1, "T1", 4)
            t2 = ensure_table(cur, r2, "T2", 2)

            cat1 = ensure_category(cur, r1, "Main", 1)
            ensure_item(cur, cat1, "Plov", "Traditional rice dish", "450.00", "KGS", 1)
            
            # Add some bookings if empty
            cur.execute("select count(*) as c from bookings")
            if cur.fetchone()["c"] == 0:
                now = datetime.now(timezone.utc)
                bid = uuid.uuid4()
                cur.execute("insert into bookings(id, restaurant_id, table_id, party_size, start_time, end_time, status, customer_user_id) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (str(bid), r1, t1, 2, now - timedelta(hours=2), now - timedelta(hours=1), "COMPLETED", cust_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
