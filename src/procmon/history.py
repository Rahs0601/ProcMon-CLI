
import click
import psycopg2
from psycopg2 import Error
from rich.console import Console
from rich.table import Table
from .db import get_db_connection

import json
import csv
from io import StringIO

def query_history(
    process_name: str = None,
    pid: int = None,
    start_time: str = None,
    end_time: str = None,
    aggregate: str = None,
    output_format: str = 'table',
    gpu: bool = False,
    gpu_index: int = None
):
    """Queries historical process data from the database."""
    console = Console()
    conn = get_db_connection()
    if not conn:
        console.print("[bold red]Error: Could not connect to the database.[/bold red]")
        return

    try:
        cur = conn.cursor()
        
        if aggregate and aggregate not in ["hourly", "daily", "weekly", "monthly"]:
            console.print("[bold red]Error: Invalid aggregate level. Choose from hourly, daily, weekly, monthly.[/bold red]")
            return

        if gpu:
            table_name = "gpu_usage"
            columns = "time, gpu_index, gpu_name, utilization_gpu, utilization_memory, temperature_gpu, fan_speed, power_usage"
            order_by = "time"
        elif aggregate:
            table_name = f"processes_{aggregate}"
            columns = "bucket, name, max_cpu_percent, avg_cpu_percent, max_memory_percent, avg_memory_percent"
            order_by = "bucket"
        else:
            table_name = "processes"
            columns = "time, pid, name, cpu_percent, memory_percent"
            order_by = "time"

        query = f"SELECT {columns} FROM {table_name} WHERE 1=1"
        params = []

        if gpu:
            if gpu_index is not None:
                query += " AND gpu_index = %s"
                params.append(gpu_index)
        else: # Process specific filters
            if process_name:
                query += " AND name ILIKE %s"
                params.append(f"%{process_name}%")
            if pid:
                query += " AND pid = %s"
                params.append(pid)
        
        if start_time:
            query += " AND time >= %s"
            params.append(start_time)
        if end_time:
            query += " AND time <= %s"
            params.append(end_time)
        
        query += f" ORDER BY {order_by} DESC LIMIT 100"

        cur.execute(query, params)
        rows = cur.fetchall()

        if not rows:
            console.print("[bold yellow]No historical data found for the given criteria.[/bold yellow]")
            return

        if output_format == 'json':
            columns_list = [desc[0] for desc in cur.description]
            result = [dict(zip(columns_list, row)) for row in rows]
            console.print(json.dumps(result, indent=4, default=str))
        elif output_format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([desc[0] for desc in cur.description])
            writer.writerows(rows)
            console.print(output.getvalue())
        else: # Default to table
            if gpu:
                table = Table(title="Historical GPU Usage Data")
                table.add_column("Timestamp", style="cyan")
                table.add_column("GPU Index", justify="right", style="cyan")
                table.add_column("GPU Name", style="magenta")
                table.add_column("GPU Util %", justify="right", style="green")
                table.add_column("Mem Util %", justify="right", style="yellow")
                table.add_column("Temp (C)", justify="right", style="red")
                table.add_column("Fan Speed %", justify="right", style="blue")
                table.add_column("Power (W)", justify="right", style="purple")
                for row in rows:
                    table.add_row(
                        str(row[0]),
                        str(row[1]),
                        str(row[2]),
                        f"{row[3]:.2f}",
                        f"{row[4]:.2f}",
                        f"{row[5]:.2f}",
                        f"{row[6]:.2f}",
                        f"{row[7]:.2f}"
                    )
            else:
                table = Table(title=f"Historical Process Data ({aggregate if aggregate else 'Raw'})")
                if aggregate:
                    table.add_column("Time Bucket", style="cyan")
                    table.add_column("Process Name", style="magenta")
                    table.add_column("Max CPU %", justify="right", style="green")
                    table.add_column("Avg CPU %", justify="right", style="green")
                    table.add_column("Max Memory %", justify="right", style="yellow")
                    table.add_column("Avg Memory %", justify="right", style="yellow")
                else:
                    table.add_column("Timestamp", style="cyan")
                    table.add_column("PID", justify="right", style="cyan")
                    table.add_column("Process Name", style="magenta")
                    table.add_column("CPU %", justify="right", style="green")
                    table.add_column("Memory %", justify="right", style="yellow")

                for row in rows:
                    if aggregate:
                        table.add_row(
                            str(row[0]),
                            str(row[1]),
                            f"{row[2]:.2f}",
                            f"{row[3]:.2f}",
                            f"{row[4]:.2f}",
                            f"{row[5]:.2f}"
                        )
                    else:
                        table.add_row(
                            str(row[0]),
                            str(row[1]),
                            str(row[2]),
                            f"{row[3]:.2f}",
                            f"{row[4]:.2f}"
                        )
            
            console.print(table)

    except Error as e:
        console.print(f"[bold red]Database error: {e}[/bold red]")
    finally:
        conn.close()

