import os
import psycopg2

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")

def inspect_schema():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        with conn.cursor() as cur:
            tables = ["bookings", "restaurants", "menu_items", "menu_categories", "restaurant_tables", "users"]
            for table in tables:
                print(f"\n--- Schema for {table} ---")
                cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
                for row in cur.fetchall():
                    print(f"  {row[0]}: {row[1]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_schema()
