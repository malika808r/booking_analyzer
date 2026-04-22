import os
from datetime import datetime, timedelta, timezone
import uuid
import psycopg2
import psycopg2.extras
from passlib.hash import bcrypt

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")

BOOTSTRAP = os.getenv("STATS_DB_BOOTSTRAP", "true").lower() == "true"
SEED = os.getenv("STATS_DB_SEED", "true").lower() == "true"

def conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

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
CREATE INDEX IF NOT EXISTS idx_restaurant_owners_owner ON restaurant_owners(owner_user_id);

CREATE TABLE IF NOT EXISTS restaurant_tables (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  label VARCHAR(128) NOT NULL,
  capacity INT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tables_restaurant ON restaurant_tables(restaurant_id);

CREATE TABLE IF NOT EXISTS menu_categories (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  sort_order INT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_menu_categories_restaurant ON menu_categories(restaurant_id);

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
CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id);

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
CREATE INDEX IF NOT EXISTS idx_bookings_table_time ON bookings(table_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_bookings_restaurant_time ON bookings(restaurant_id, start_time);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

CREATE TABLE IF NOT EXISTS contact_requests (
  id UUID PRIMARY KEY,
  restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
  customer_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  customer_name VARCHAR(255),
  customer_phone VARCHAR(64),
  customer_email VARCHAR(255),
  message TEXT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_contact_requests_restaurant ON contact_requests(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_contact_requests_status ON contact_requests(status);
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

def seed_bookings_if_none(cur, customer_user_id, r1_id, r2_id, t_r1, t_r2):
    cur.execute("select count(*) as c from bookings")
    if cur.fetchone()["c"] > 0: return

    now = datetime.now(timezone.utc)
    def ins(restaurant_id, table_id, party_size, start_dt, end_dt, status):
        bid = uuid.uuid4()
        cur.execute("insert into bookings(id, restaurant_id, table_id, party_size, start_time, end_time, status, customer_user_id) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (str(bid), restaurant_id, table_id, party_size, start_dt, end_dt, status, customer_user_id))

    s = (now - timedelta(days=5)).replace(hour=18, minute=0, second=0, microsecond=0)
    ins(r1_id, t_r1, 2, s, s + timedelta(hours=1), "COMPLETED")
    s = (now - timedelta(days=3)).replace(hour=19, minute=0, second=0, microsecond=0)
    ins(r2_id, t_r2, 4, s, s + timedelta(hours=1), "NO_SHOW")
    s = (now - timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0)
    ins(r1_id, t_r1, 2, s, s + timedelta(hours=1), "CANCELLED")
    s = (now + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
    ins(r1_id, t_r1, 3, s, s + timedelta(hours=1), "BOOKED")

def main():
    print("Connecting to DB for bootstrap/seed...")
    c = conn()
    c.autocommit = False
    try:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if BOOTSTRAP:
                print("Bootstrapping schema...")
                cur.execute(SCHEMA_SQL)
            if SEED:
                print("Seeding dummy data (idempotent)...")
                mod_id = upsert_user(cur, "MODERATOR", "mod@example.com", None, "mod123456")
                owner1_id = upsert_user(cur, "OWNER", "owner1@example.com", None, "owner123456")
                owner2_id = upsert_user(cur, "OWNER", "owner2@example.com", None, "owner123456")
                cust_id = upsert_user(cur, "CUSTOMER", "cust1@example.com", None, "cust123456")

                r1 = upsert_restaurant(cur, "Demo Restaurant A", "Seed restaurant A", "Bishkek A", "+996000000001")
                r2 = upsert_restaurant(cur, "Demo Restaurant B", "Seed restaurant B", "Bishkek B", "+996000000002")

                ensure_owner_link(cur, r1, owner1_id)
                ensure_owner_link(cur, r2, owner1_id)
                ensure_owner_link(cur, r2, owner2_id)

                t1 = ensure_table(cur, r1, "T1", 4)
                t2 = ensure_table(cur, r2, "T1", 4)

                cat1 = ensure_category(cur, r1, "Main", 1)
                ensure_item(cur, cat1, "Plov", "Traditional rice dish", "450.00", "KGS", 1)

                seed_bookings_if_none(cur, cust_id, r1, r2, t1, t2)
        c.commit()
        print("Bootstrap/seed done. 🎉")
    except Exception as e:
        c.rollback()
        print("Bootstrap failed:", e)
    finally:
        c.close()

if __name__ == "__main__":
    main()