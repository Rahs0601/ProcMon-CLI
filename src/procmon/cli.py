
import click
from rich.console import Console
from rich.table import Table
import psutil
import time
from .db import setup_database
from .collector import collect_data, read_pid_file, delete_pid_file, PID_FILE, HAS_NVML
from .history import query_history
import os
import signal

@click.group()
def main():
    """A CLI for monitoring system processes."""
    pass

from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.layout import Layout

@main.command()
def live():
    """Display a live view of system processes."""
    console = Console()

    def generate_layout() -> Layout:
        # Header
        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)
        disk_io = psutil.disk_io_counters()

        mem_bar = ProgressBar(total=100, completed=mem.percent, width=40)
        cpu_bar = ProgressBar(total=100, completed=cpu_percent, width=40)

        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="left", ratio=2)
        grid.add_row(f"[bold green]CPU Usage[/]: {cpu_percent:.1f}%", cpu_bar)
        grid.add_row(f"[bold yellow]Mem Usage[/]: {mem.used/1024**3:.2f}G/{mem.total/1024**3:.2f}G ({mem.percent}%)", mem_bar)

        if HAS_NVML:
            from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, nvmlDeviceGetUtilizationRates, nvmlShutdown, NVMLError
            try:
                nvmlInit()
                device_count = nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = nvmlDeviceGetHandleByIndex(i)
                    utilization = nvmlDeviceGetUtilizationRates(handle)
                    gpu_percent = utilization.gpu
                    gpu_bar = ProgressBar(total=100, completed=gpu_percent, width=40)
                    grid.add_row(f"[bold red]GPU {i} Usage[/]: {gpu_percent:.1f}%", gpu_bar)
            except NVMLError:
                pass # Fail silently if we can't get GPU info for the overview
            finally:
                try:
                    nvmlShutdown()
                except NVMLError:
                    pass
        
        if disk_io:
            grid.add_row(f"[bold blue]Disk I/O[/]: Read {disk_io.read_bytes/1024**3:.2f} GB / Write {disk_io.write_bytes/1024**3:.2f} GB")

        # Process Table
        table = Table(title="Processes")
        table.add_column("PID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Process Name", style="magenta")
        table.add_column("CPU %", justify="right", style="green")
        table.add_column("Memory %", justify="right", style="yellow")
        table.add_column("Read (MB)", justify="right", style="blue")
        table.add_column("Write (MB)", justify="right", style="red")

        processes = sorted(
            psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'io_counters']),
            key=lambda p: p.info['cpu_percent'],
            reverse=True
        )

        for proc in processes[:console.height - 10]:  # Adjust for header
            try:
                io_counters = proc.info.get('io_counters')
                read_mb = io_counters.read_bytes / 1024**2 if io_counters else 0
                write_mb = io_counters.write_bytes / 1024**2 if io_counters else 0
                table.add_row(
                    str(proc.info['pid']),
                    proc.info['name'],
                    f"{proc.info['cpu_percent']:.2f}",
                    f"{proc.info['memory_percent']:.2f}",
                    f"{read_mb:.2f}",
                    f"{write_mb:.2f}",
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        layout = Layout()
        if HAS_NVML:
            from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, nvmlDeviceGetName, nvmlDeviceGetUtilizationRates, nvmlShutdown, NVMLError, NVML_TEMPERATURE_GPU, nvmlDeviceGetTemperature, nvmlDeviceGetFanSpeed, nvmlDeviceGetPowerUsage
            gpu_table = Table(title="GPU Usage")
            gpu_table.add_column("GPU", style="cyan")
            gpu_table.add_column("Name", style="magenta")
            gpu_table.add_column("GPU Util %", justify="right", style="green")
            gpu_table.add_column("Mem Util %", justify="right", style="yellow")
            gpu_table.add_column("Temp (C)", justify="right", style="red")
            gpu_table.add_column("Fan Speed %", justify="right", style="blue")
            gpu_table.add_column("Power (W)", justify="right", style="purple")

            try:
                nvmlInit()
                device_count = nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = nvmlDeviceGetHandleByIndex(i)
                    gpu_name = nvmlDeviceGetName(handle)
                    
                    try:
                        utilization = nvmlDeviceGetUtilizationRates(handle)
                        gpu_util = f"{utilization.gpu:.1f}"
                        mem_util = f"{utilization.memory:.1f}"
                    except NVMLError:
                        gpu_util = "N/A"
                        mem_util = "N/A"

                    try:
                        temperature = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                        temp_str = f"{temperature:.1f}"
                    except NVMLError:
                        temp_str = "N/A"

                    try:
                        fan_speed = nvmlDeviceGetFanSpeed(handle)
                        fan_str = f"{fan_speed:.1f}"
                    except NVMLError:
                        fan_str = "N/A"

                    try:
                        power_usage = nvmlDeviceGetPowerUsage(handle) / 1000  # Convert mW to W
                        power_str = f"{power_usage:.1f}"
                    except NVMLError:
                        power_str = "N/A"

                    gpu_table.add_row(
                        str(i),
                        gpu_name,
                        gpu_util,
                        mem_util,
                        temp_str,
                        fan_str,
                        power_str
                    )
            except NVMLError as error:
                gpu_table = Panel(f"[red]NVML Error: {error}[/red]", title="GPU Usage")
            finally:
                try:
                    nvmlShutdown()
                except NVMLError as error:
                    pass # Already handled, or not initialized

            layout.split(
                Layout(Panel(grid, title="System Overview", border_style="green"), size=5),
                Layout(Panel(gpu_table, border_style="red")),
                Layout(Panel(table, border_style="blue"))
            )
        else:
            layout.split(
                Layout(Panel(grid, title="System Overview", border_style="green"), size=5),
                Layout(Panel(table, border_style="blue"))
            )
        return layout

    with Live(generate_layout(), screen=True, transient=True, refresh_per_second=2) as live:
        while True:
            live.update(generate_layout())
            time.sleep(0.5)

@main.command()
def setup_db():
    """Set up the PostgreSQL database with TimescaleDB extension and continuous aggregates."""
    click.echo("Setting up database...")
    setup_database()
    click.echo("Database setup complete.")

import subprocess

@main.command()
def start_collector():
    """Starts the background data collection service."""
    click.echo("Starting data collector in the background...")
    try:
        # Use subprocess to run collector.py in the background
        subprocess.Popen(["python", "-m", "src.procmon.collector"])
        click.echo("Data collector started. You can close this terminal.")
    except Exception as e:
        click.echo(f"Error starting collector: {e}")

@main.command()
def stop_collector():
    """Stops the background data collection service."""
    pid = read_pid_file()
    if pid:
        try:
            if sys.platform == "win32":
                os.kill(pid, signal.CTRL_C_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
            delete_pid_file()
            click.echo(f"Collector (PID: {pid}) stopped.")
        except ProcessLookupError:
            click.echo(f"Collector (PID: {pid}) not found. Removing stale PID file.")
            delete_pid_file()
        except Exception as e:
            click.echo(f"Error stopping collector: {e}")
    else:
        click.echo("Collector is not running (PID file not found).")

@main.command()
def status_collector():
    """Checks the status of the background data collection service."""
    pid = read_pid_file()
    if pid:
        if psutil.pid_exists(pid):
            try:
                p = psutil.Process(pid)
                click.echo(f"Collector is running with PID: {pid} (Name: {p.name()}, Status: {p.status()})")
            except psutil.NoSuchProcess:
                click.echo(f"Collector (PID: {pid}) not found, but PID file exists. Removing stale PID file.")
                delete_pid_file()
        else:
            click.echo(f"Collector (PID: {pid}) not running. Removing stale PID file.")
            delete_pid_file()
    else:
        click.echo("Collector is not running.")

@main.command()
@click.option('--process-name', '-n', help='Filter by process name (case-insensitive, partial match).')
@click.option('--pid', '-p', type=int, help='Filter by process ID.')
@click.option('--start-time', '-s', help='Start time for the query (e.g., "2023-01-01", "2 hours ago").')
@click.option('--end-time', '-e', help='End time for the query (e.g., "2023-01-02", "now").')
@click.option('--aggregate', '-a', type=click.Choice(['hourly', 'daily', 'weekly', 'monthly']), help='Aggregate data by hour, day, week, or month.')
@click.option('--output-format', '-o', type=click.Choice(['table', 'json', 'csv']), default='table', help='Output format for the historical data.')
@click.option('--gpu', is_flag=True, help='Query GPU usage history.')
@click.option('--gpu-index', type=int, help='Filter GPU usage by GPU index.')
def history(process_name, pid, start_time, end_time, aggregate, output_format, gpu, gpu_index):
    """Query historical process data."""
    query_history(process_name, pid, start_time, end_time, aggregate, output_format)

if __name__ == "__main__":
    main()
