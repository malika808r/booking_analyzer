import os
import random
import uuid
from datetime import datetime, timedelta, timezone
import psycopg2
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

def generate_data(num_records=10000):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. Get a restaurant and its tables
            cur.execute("SELECT id FROM restaurants LIMIT 1")
            res = cur.fetchone()
            if not res:
                print("Error: No restaurants found. Run bootstrap first.")
                return
            rid = res[0]

            cur.execute("SELECT id FROM restaurant_tables WHERE restaurant_id = %s", (rid,))
            table_ids = [r[0] for r in cur.fetchall()]
            if not table_ids:
                print("Error: No tables found for restaurant.")
                return

            print(f"Generating {num_records} bookings for restaurant {rid}...")

            # 2. Define VIP customers
            vips = [
                ("Alexander G.", "+996111111"),
                ("Dmitry K.", "+996222222"),
                ("Elena M.", "+996333333"),
                ("Maria S.", "+996444444"),
                ("Ivan P.", "+996555555")
            ]
            
            random_names = ["John", "Alice", "Bob", "Charlie", "Diana", "Emily", "Frank", "Grace"]
            
            bookings = []
            start_date = datetime.now() - timedelta(days=365)
            
            for i in range(num_records):
                # Seasonality: Summer months (6, 7, 8) get 2x weight
                # Peak Days: Fri (4) and Sat (5) get 3x weight
                
                while True:
                    days_offset = random.randint(0, 365)
                    dt = start_date + timedelta(days=days_offset)
                    
                    weight = 1
                    if dt.month in [6, 7, 8]: weight += 2
                    if dt.weekday() in [4, 5]: weight += 3
                    
                    if random.randint(1, 10) <= weight + 2: # Probability filter
                        break
                
                # Random time between 12:00 and 22:00
                hour = random.randint(12, 22)
                minute = random.choice([0, 15, 30, 45])
                start_time = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=2)
                
                # Pick Customer (20% chance it's a VIP)
                if random.random() < 0.2:
                    name, phone = random.choice(vips)
                else:
                    name = f"{random.choice(random_names)} {random.randint(100, 999)}"
                    phone = f"+996{random.randint(500000000, 999999999)}"
                
                # Status distribution
                status_roll = random.random()
                if status_roll < 0.7: status = "COMPLETED"
                elif status_roll < 0.85: status = "CANCELLED"
                elif status_roll < 0.95: status = "BOOKED"
                else: status = "NO_SHOW"
                
                bookings.append((
                    str(uuid.uuid4()),
                    rid,
                    random.choice(table_ids),
                    random.randint(1, 6),
                    start_time,
                    end_time,
                    status,
                    name,
                    phone
                ))

            # 3. Batch Insert
            print("Inserting into database...")
            execute_values(cur, """
                INSERT INTO bookings (id, restaurant_id, table_id, party_size, start_time, end_time, status, customer_name, customer_phone)
                VALUES %s
            """, bookings)
            
            conn.commit()
            print(f"Successfully injected {len(bookings)} bookings!")

    finally:
        conn.close()

if __name__ == "__main__":
    generate_data()
