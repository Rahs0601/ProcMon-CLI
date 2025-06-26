import psycopg2
from psycopg2 import Error
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://procmon:password@localhost:5432/procmon")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def setup_database(conn=None):
    _conn = conn if conn else get_db_connection()
    if _conn:
        try:
            cur = _conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS processes (id SERIAL PRIMARY KEY);")
            _conn.commit()
        except Error as e:
            print(f"Error setting up database: {e}")
        finally:
            if not conn and _conn: # Only close if connection was opened by this function
                _conn.close()