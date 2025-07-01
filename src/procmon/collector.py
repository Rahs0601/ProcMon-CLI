
import psutil
import time
from psycopg2 import Error
from .db import get_db_connection
import os
import tempfile

try:
    from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, nvmlDeviceGetName, nvmlDeviceGetUtilizationRates, nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU, nvmlDeviceGetFanSpeed, nvmlDeviceGetPowerUsage, NVMLError, nvmlShutdown
    HAS_NVML = True
except ImportError:
    HAS_NVML = False

PID_FILE = os.path.join(tempfile.gettempdir(), "procmon_collector.pid")

MAX_RETRIES = 5
RETRY_DELAY = 5 # seconds

def write_pid_file():
    pid = os.getpid()
    with open(PID_FILE, "w") as f:
        f.write(str(pid))

def read_pid_file():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

def delete_pid_file():
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def retry_get_db_connection():
    for i in range(MAX_RETRIES):
        conn = get_db_connection()
        if conn:
            return conn
        print(f"Attempt {i+1}/{MAX_RETRIES}: Could not connect to database. Retrying in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)
    print("Failed to connect to database after multiple retries. Exiting collector.")
    return None

def collect_data():
    """Collects process data and inserts it into the database."""
    write_pid_file()
    conn = retry_get_db_connection()
    if not conn:
        delete_pid_file()
        return

    try:
        cur = conn.cursor()
        while True:
            processes_data = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name']
                    cpu_percent = proc.info['cpu_percent']
                    memory_percent = proc.info['memory_percent']
                    processes_data.append((pid, name, cpu_percent, memory_percent))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if processes_data:
                try:
                    cur.executemany(
                        "INSERT INTO processes (time, pid, name, cpu_percent, memory_percent) VALUES (NOW(), %s, %s, %s, %s)",
                        processes_data
                    )
                    conn.commit()
                except Error as e:
                    print(f"Database error during insertion: {e}")
                    conn.rollback()
                    # Attempt to reconnect if there's a database error during insertion
                    conn.close()
                    conn = retry_get_db_connection()
                    if not conn:
                        break # Exit if reconnection fails
                    cur = conn.cursor() # Get new cursor from new connection

            if HAS_NVML:
                gpu_data = collect_gpu_data()
                if gpu_data:
                    try:
                        cur.executemany(
                            "INSERT INTO gpu_usage (time, gpu_index, gpu_name, utilization_gpu, utilization_memory, temperature_gpu, fan_speed, power_usage) VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)",
                            gpu_data
                        )
                        conn.commit()
                    except Error as e:
                        print(f"Database error during GPU data insertion: {e}")
                        conn.rollback()
                        conn.close()
                        conn = retry_get_db_connection()
                        if not conn:
                            break
                        cur = conn.cursor()

            time.sleep(5) # Collect data every 5 seconds

    except KeyboardInterrupt:
        print("Data collection stopped.")
    except Exception as e:
        print(f"An unexpected error occurred during data collection: {e}")
    finally:
        if conn:
            conn.close()
        delete_pid_file()

def collect_gpu_data():
    gpu_metrics = []
    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        for i in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(i)
            gpu_name = nvmlDeviceGetName(handle)
            utilization = nvmlDeviceGetUtilizationRates(handle)
            temperature = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
            fan_speed = nvmlDeviceGetFanSpeed(handle)
            power_usage = nvmlDeviceGetPowerUsage(handle) / 1000 # Convert mW to W

            gpu_metrics.append((
                i,
                gpu_name,
                utilization.gpu,
                utilization.memory,
                temperature,
                fan_speed,
                power_usage
            ))
    except NVMLError as error:
        print(f"NVML Error: {error}")
    finally:
        try:
            nvmlShutdown()
        except NVMLError as error:
            print(f"NVML Shutdown Error: {error}")
    return gpu_metrics

if __name__ == "__main__":
    collect_data()
