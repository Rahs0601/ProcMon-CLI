import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from src.procmon.db import setup_database
import os

@pytest.fixture(scope="session")
def test_db(request):
    """Creates a test database for the session and tears it down afterwards."""
    # Use a fixed test database name
    test_db_name = "test_procmon"
    os.environ["DATABASE_URL"] = f"postgresql://procmon:password@localhost:5432/{test_db_name}"

    # Connect to the default `postgres` database to manage the test database
    conn = psycopg2.connect(dbname='postgres', user='procmon', host='localhost', password='password')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    cur.execute(f"DROP DATABASE IF EXISTS {test_db_name};")
    cur.execute(f"CREATE DATABASE {test_db_name};")
    
    cur.close()
    conn.close()

    # Now connect to the new test database to set it up
    test_conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        setup_database(test_conn) # Pass the connection to the setup function
    finally:
        test_conn.close()

    # Yield control to the tests
    yield

    # Teardown: connect to postgres db again to drop the test database
    conn = psycopg2.connect(dbname='postgres', user='procmon', host='localhost', password='password')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE {test_db_name};")
    cur.close()
    conn.close()

@pytest.fixture(scope="function")
def db_connection(test_db):
    """Provides a fresh database connection for each test function."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    yield conn
    conn.close()