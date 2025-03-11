import psycopg2

def initialize_database():
    """Ensure the database and users table exist with SERIAL ID starting from 1."""
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='2003', host='127.0.0.1',port='1234')
    conn.autocommit = True
    cursor = conn.cursor()

    # Create database if not exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'chat_app'")
    if not cursor.fetchone():
        cursor.execute("CREATE DATABASE chat_app")

    cursor.close()
    conn.close()

    # Connect to chat_app and create users table
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='2003', host='127.0.0.1',port='1234')
    cursor = conn.cursor()
    
    # Drop the table to reset the ID sequence (BE CAREFUL in production!)
    cursor.execute("DROP TABLE IF EXISTS users")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            personality TEXT
        );
    """)
    
    # Reset the ID sequence to start from 1
    cursor.execute("ALTER SEQUENCE users_id_seq RESTART WITH 1")
    
    conn.commit()
    cursor.close()
    conn.close()

    print("Database and table are created.")