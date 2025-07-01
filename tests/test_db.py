

def test_db_connection(db_connection):
    assert db_connection is not None

def test_setup_database(db_connection):
    cur = db_connection.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'processes';")
    assert cur.fetchone() is not None