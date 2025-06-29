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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS processes (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    pid INTEGER,
                    name VARCHAR(255),
                    cpu_percent REAL,
                    memory_percent REAL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gpu_usage (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    gpu_index INTEGER,
                    gpu_name VARCHAR(255),
                    utilization_gpu REAL,
                    utilization_memory REAL,
                    temperature_gpu REAL,
                    fan_speed REAL,
                    power_usage REAL
                );
            """)
            _conn.commit()
        except Error as e:
            print(f"Error setting up database: {e}")
        finally:
            if not conn and _conn: # Only close if connection was opened by this function
                _conn.close()