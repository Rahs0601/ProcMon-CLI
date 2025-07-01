import subprocess
import sys
import click
from rich.console import Console
from rich.table import Table
import psutil
import time
from .db import setup_database
from .collector import read_pid_file, delete_pid_file, HAS_NVML
from .history import query_history
import os
import signal
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.layout import Layout
from rich.text import Text

@click.group()
def main():
    """A CLI for monitoring system processes."""
    pass

@main.command()
def live():
    """Display a live view of system processes."""
    console = Console()
    last_sort_time = 0
    process_list = []

    def generate_layout() -> Layout:
        nonlocal last_sort_time, process_list
        
        # Get terminal dimensions
        terminal_width = console.size.width
        terminal_height = console.size.height
        
        # Calculate dynamic widths
        progress_bar_width = max(20, min(50, terminal_width // 3))
        
        # Header with system overview
        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)
        disk_io = psutil.disk_io_counters()

        mem_bar = ProgressBar(total=100, completed=mem.percent, width=progress_bar_width)
        cpu_bar = ProgressBar(total=100, completed=cpu_percent, width=progress_bar_width)

        # Dynamic grid layout
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", min_width=20, ratio=1)
        grid.add_column(justify="left", min_width=progress_bar_width, ratio=2)
        
        grid.add_row(f"[bold green]CPU Usage[/]: {cpu_percent:.1f}%", cpu_bar)
        grid.add_row(
            f"[bold yellow]Memory[/]: {mem.used/1024**3:.1f}G/{mem.total/1024**3:.1f}G ({mem.percent:.1f}%)", 
            mem_bar
        )

        gpu_rows = 0
        if HAS_NVML:
            from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, nvmlDeviceGetUtilizationRates, nvmlShutdown, NVMLError
            try:
                nvmlInit()
                device_count = nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = nvmlDeviceGetHandleByIndex(i)
                    utilization = nvmlDeviceGetUtilizationRates(handle)
                    gpu_percent = utilization.gpu
                    gpu_bar = ProgressBar(total=100, completed=gpu_percent, width=progress_bar_width)
                    grid.add_row(f"[bold red]GPU {i}[/]: {gpu_percent:.1f}%", gpu_bar)
                    gpu_rows += 1
            except NVMLError:
                pass
            finally:
                try:
                    nvmlShutdown()
                except NVMLError:
                    pass
        
        disk_rows = 0
        if disk_io:
            disk_text = f"[bold blue]Disk I/O[/]: R:{disk_io.read_bytes/1024**3:.1f}GB W:{disk_io.write_bytes/1024**3:.1f}GB"
            grid.add_row(disk_text, "")
            disk_rows = 1

        # Calculate dynamic process table dimensions
        overview_rows = 2 + gpu_rows + disk_rows  # CPU, Memory + GPUs + Disk
        overview_panel_height = overview_rows * 2  # Add padding for panel borders and title

        # Dynamic GPU panel
        gpu_panel_item = None
        gpu_panel_height = 0
        
        if HAS_NVML:
            from pynvml import (nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, 
                              nvmlDeviceGetName, nvmlDeviceGetUtilizationRates, nvmlShutdown, 
                              NVMLError, NVML_TEMPERATURE_GPU, nvmlDeviceGetTemperature, 
                              nvmlDeviceGetFanSpeed, nvmlDeviceGetPowerUsage)
            
            try:
                nvmlInit()
                device_count = nvmlDeviceGetCount()
                if device_count > 0:
                    # Calculate dynamic column widths for GPU table
                    gpu_table_width = min(terminal_width - 4, 120)  # Leave margin, max 120
                    
                    gpu_table = Table(title="GPU Details", width=gpu_table_width, expand=True)
                    
                    # Dynamic column widths based on terminal size
                    col_widths = {
                        'gpu': max(4, terminal_width // 20),
                        'name': max(10, terminal_width // 8),
                        'gpu_util': max(8, terminal_width // 15),
                        'mem_util': max(8, terminal_width // 15),
                        'temp': max(8, terminal_width // 15),
                        'fan': max(8, terminal_width // 15),
                        'power': max(8, terminal_width // 15)
                    }
                    
                    gpu_table.add_column("GPU", style="cyan", width=col_widths['gpu'])
                    gpu_table.add_column("Name", style="magenta", width=col_widths['name'])
                    gpu_table.add_column("GPU%", justify="right", style="green", width=col_widths['gpu_util'])
                    gpu_table.add_column("Mem%", justify="right", style="yellow", width=col_widths['mem_util'])
                    gpu_table.add_column("Temp°C", justify="right", style="red", width=col_widths['temp'])
                    gpu_table.add_column("Fan%", justify="right", style="blue", width=col_widths['fan'])
                    gpu_table.add_column("Power W", justify="right", style="purple", width=col_widths['power'])

                    for i in range(device_count):
                        handle = nvmlDeviceGetHandleByIndex(i)
                        
                        try:
                            gpu_name = nvmlDeviceGetName(handle)
                            # Truncate long GPU names to fit
                            # if len(gpu_name) > col_widths['name']:
                                # gpu_name = gpu_name[:col_widths['name']] + "..."
                        except NVMLError:
                            gpu_name = "Unknown"
                        
                        # Get all GPU metrics with error handling
                        try:
                            utilization = nvmlDeviceGetUtilizationRates(handle)
                            gpu_util = f"{utilization.gpu:.0f}"
                            mem_util = f"{utilization.memory:.0f}"
                        except NVMLError:
                            gpu_util = "N/A"
                            mem_util = "N/A"

                        try:
                            temperature = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                            temp_str = f"{temperature:.0f}"
                        except NVMLError:
                            temp_str = "N/A"

                        try:
                            fan_speed = nvmlDeviceGetFanSpeed(handle)
                            fan_str = f"{fan_speed:.0f}"
                        except NVMLError:
                            fan_str = "N/A"

                        try:
                            power_usage = nvmlDeviceGetPowerUsage(handle) / 1000
                            power_str = f"{power_usage:.0f}"
                        except NVMLError:
                            power_str = "N/A"

                        gpu_table.add_row(str(i), gpu_name, gpu_util, mem_util, temp_str, fan_str, power_str)
                    
                    gpu_panel_height = device_count + 8  # rows + header + borders + title
                    gpu_panel_item = Panel(gpu_table, border_style="red", expand=True)
                    
            except NVMLError:
                pass
            finally:
                try:
                    nvmlShutdown()
                except NVMLError:
                    pass

        # Dynamic Process Table
        available_height = terminal_height - overview_panel_height - gpu_panel_height - 2
        max_processes = max(5, available_height - 4)  # Minimum 5 processes, adjust for table header/borders
        
        table_width = min(terminal_width - 2, 140)  # Dynamic width with reasonable maximum
        
        table = Table(title="Top Processes", width=table_width, expand=True)
        
        # Calculate dynamic column widths based on terminal size
        col_ratios = {
            'pid': max(6, terminal_width // 25),
            'name': max(15, terminal_width // 6),
            'cpu': max(8, terminal_width // 18),
            'memory': max(10, terminal_width // 15),
            'read': max(10, terminal_width // 15),
            'write': max(10, terminal_width // 15)
        }
        
        table.add_column("PID", justify="right", style="cyan", no_wrap=True, width=col_ratios['pid'])
        table.add_column("Process Name", style="magenta", width=col_ratios['name'])
        table.add_column("CPU %", justify="right", style="green", width=col_ratios['cpu'])
        table.add_column("Memory %", justify="right", style="yellow", width=col_ratios['memory'])
        table.add_column("Read MB", justify="right", style="blue", width=col_ratios['read'])
        table.add_column("Write MB", justify="right", style="red", width=col_ratios['write'])

        # Update process list periodically
        current_time = time.time()
        if current_time - last_sort_time > 2:
            last_sort_time = current_time
            try:
                process_list = sorted(
                    psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'io_counters']),
                    key=lambda p: p.info.get('cpu_percent', 0) or 0,
                    reverse=True
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_list = []

        # Add processes to table
        added_processes = 0
        for proc in process_list:
            if added_processes >= max_processes:
                break
                
            try:
                pid = proc.info.get('pid', 'N/A')
                name = proc.info.get('name', 'Unknown')
                cpu_pct = proc.info.get('cpu_percent', 0) or 0
                mem_pct = proc.info.get('memory_percent', 0) or 0
                
                # Truncate long process names
                # if len(name) > col_ratios['name'] - 2:
                #     name = name[:col_ratios['name'] - 5] + "..."
                
                io_counters = proc.info.get('io_counters')
                if io_counters:
                    read_mb = io_counters.read_bytes / 1024**2
                    write_mb = io_counters.write_bytes / 1024**2
                else:
                    read_mb = write_mb = 0
                
                table.add_row(
                    str(pid),
                    name,
                    f"{cpu_pct:.1f}",
                    f"{mem_pct:.1f}",
                    f"{read_mb:.1f}",
                    f"{write_mb:.1f}",
                )
                added_processes += 1
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                last_sort_time = 0  # Force refresh
                continue

        # Create dynamic layout
        layout = Layout()
        
        # Calculate section ratios based on content
        sections = []
        section_sizes = []
        
        # System Overview (always present)
        sections.append(Layout(Panel(grid, title="System Overview", border_style="green"), 
                              size=overview_panel_height))
        
        # GPU Panel (if available)
        if gpu_panel_item:
            sections.append(Layout(gpu_panel_item, size=gpu_panel_height))
        
        # Process Table (remaining space)
        sections.append(Layout(Panel(table, border_style="blue")))
        
        # Split layout dynamically
        layout.split(*sections)
        return layout

    # Start the live display
    with Live(generate_layout(), screen=True, transient=True, refresh_per_second=1) as live:
        try:
            while True:
                live.update(generate_layout())
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass

@main.command()
def setup_db():
    """Set up the PostgreSQL database with TimescaleDB extension and continuous aggregates."""
    click.echo("Setting up database...")
    setup_database()
    click.echo("Database setup complete.")

@main.command()
def start_collector():
    """Starts the background data collection service."""
    click.echo("Starting data collector in the background...")
    try:
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
    query_history(process_name, pid, start_time, end_time, aggregate, output_format, gpu, gpu_index)

if __name__ == "__main__":
    main()