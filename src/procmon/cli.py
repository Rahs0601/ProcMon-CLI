
import click
from rich.console import Console
from rich.table import Table
import psutil
import time
from .db import setup_database
from .collector import collect_data, read_pid_file, delete_pid_file, PID_FILE
from .history import query_history
import os
import signal

@click.group()
def main():
    """A CLI for monitoring system processes."""
    pass

from rich.live import Live

@main.command()
def live():
    """Display a live view of system processes."""
    console = Console()

    def generate_table() -> Table:
        table = Table(title="Live Process Monitor")
        table.add_column("PID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Process Name", style="magenta")
        table.add_column("CPU %", justify="right", style="green")
        table.add_column("Memory %", justify="right", style="yellow")

        processes = sorted(
            psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
            key=lambda p: p.info['cpu_percent'],
            reverse=True
        )

        for proc in processes[:console.height - 4]:  # Limit to screen height
            try:
                table.add_row(
                    str(proc.info['pid']),
                    proc.info['name'],
                    f"{proc.info['cpu_percent']:.2f}",
                    f"{proc.info['memory_percent']:.2f}",
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return table

    with Live(generate_table(), screen=True, transient=True) as live:
        while True:
            live.update(generate_table())
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
def history(process_name, pid, start_time, end_time, aggregate, output_format):
    """Query historical process data."""
    query_history(process_name, pid, start_time, end_time, aggregate, output_format)

if __name__ == "__main__":
    main()
