import os
import random
import uuid
from datetime import datetime, timedelta, timezone
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

# --- DB CONFIG ---
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def generate_data(num_records_per_res=2000):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Get all restaurants
            cur.execute("SELECT id, name FROM restaurants")
            restaurants = cur.fetchall()
            if not restaurants:
                print("Error: No restaurants found. Run bootstrap first.")
                return

            vips = [
                ("Alexander G.", "+996111111"), ("Dmitry K.", "+996222222"),
                ("Elena M.", "+996333333"), ("Maria S.", "+996444444"), ("Ivan P.", "+996555555")
            ]
            random_names = ["John", "Alice", "Bob", "Charlie", "Diana", "Emily", "Frank", "Grace"]

            for res in restaurants:
                rid = res["id"]
                name = res["name"]
                cur.execute("SELECT id FROM restaurant_tables WHERE restaurant_id = %s", (rid,))
                table_ids = [r["id"] for r in cur.fetchall()]
                if not table_ids: continue

                print(f"Generating data for {name} ({rid})...")
                bookings = []
                start_date = datetime.now() - timedelta(days=365)

                # Variability factors per restaurant
                cancel_prob = random.uniform(0.05, 0.25) # Some have more cancels
                noshow_prob = random.uniform(0.02, 0.10)
                weekend_bias = random.choice([2, 5, 8]) # Some are much busier on weekends
                
                for i in range(num_records_per_res):
                    while True:
                        days_offset = random.randint(0, 365)
                        dt = start_date + timedelta(days=days_offset)
                        weight = 1
                        if dt.month in [6, 7, 8]: weight += 2
                        if dt.weekday() in [4, 5]: weight += weekend_bias
                        if random.randint(1, 15) <= weight + 2: break
                    
                    hour = random.randint(12, 22)
                    minute = random.choice([0, 15, 30, 45])
                    start_time = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    end_time = start_time + timedelta(hours=2)
                    
                    if random.random() < 0.2:
                        c_name, c_phone = random.choice(vips)
                    else:
                        c_name = f"{random.choice(random_names)} {random.randint(100, 999)}"
                        c_phone = f"+996{random.randint(500000000, 999999999)}"
                    
                    status_roll = random.random()
                    if status_roll < (1 - cancel_prob - noshow_prob): status = "COMPLETED"
                    elif status_roll < (1 - noshow_prob): status = "CANCELLED"
                    else: status = "NO_SHOW"
                    
                    bookings.append((
                        str(uuid.uuid4()), rid, random.choice(table_ids),
                        random.randint(1, 6), start_time, end_time, status, c_name, c_phone
                    ))

                execute_values(cur, """
                    INSERT INTO bookings (id, restaurant_id, table_id, party_size, start_time, end_time, status, customer_name, customer_phone)
                    VALUES %s
                """, bookings)
                conn.commit()
                print(f"-> Injected {len(bookings)} records for {name}.")

    finally:
        conn.close()

if __name__ == "__main__":
    generate_data()
