import sqlite3
import os

# Get the absolute path to the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "prodsmart.db")

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    # This allows accessing columns by name if needed, though not strictly necessary
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    """Creates the tasks table with the correct schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # We use the schema that includes is_urgent, is_important, etc.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            due_date TEXT,
            priority TEXT,
            is_urgent INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()