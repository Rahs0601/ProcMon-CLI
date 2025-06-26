# ProcMon-CLI

A CLI tool for monitoring system processes and their resource usage, with historical data storage in TimescaleDB.

## Features

- Live process monitoring (CPU, Memory)
- Historical data collection and storage in TimescaleDB
- Aggregated historical data (hourly, daily, weekly, monthly)

## Setup

### 1. Database Setup (TimescaleDB with Docker)

Ensure you have Docker and Docker Compose installed.

Navigate to the `ProcMon-CLI` directory and run:

```bash
docker-compose up -d
```

This will start a PostgreSQL container with TimescaleDB enabled on port `5432`.

### 2. Application Setup

It's recommended to use `poetry` for dependency management.

```bash
# Install poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Navigate to the project directory
cd ProcMon-CLI

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

## Usage

### Live Monitoring

To view real-time process information:

```bash
procmon live
```

### Historical Data Collection

To start the background data collection service, run:

```bash
procmon start-collector
```

This will run the collector in the background, continuously collecting process data.

To check the status of the collector:

```bash
procmon status-collector
```

To stop the collector:

```bash
procmon stop-collector
```

### Querying Historical Data

To query historical process data, use the `history` command. You can filter by process name, PID, time range, and aggregate data.

```bash
procmon history --process-name python --start-time "2 hours ago" --aggregate hourly
procmon history --pid 1234 --end-time "now"
procmon history -n chrome -s "2023-01-01" -e "2023-01-02" -a daily
```

**Output Formats:**
You can specify the output format using the `-o` or `--output-format` option. Supported formats are `table` (default), `json`, and `csv`.

```bash
procmon history -n python -o json
procmon history -a daily -o csv
```
