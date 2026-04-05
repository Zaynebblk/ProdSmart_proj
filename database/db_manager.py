import sqlite3
import os
import hashlib

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
            created_date TEXT,
            completed_at TEXT,
            task_type TEXT,
            is_urgent INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN created_date TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pomodoro_sessions ADD COLUMN task_priority TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pomodoro_sessions ADD COLUMN task_type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN latitude REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN longitude REAL")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, latitude=None, longitude=None):
    """Create a new user account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, latitude, longitude) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), latitude, longitude)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def authenticate_user(username, password):
    """Authenticate a user. Returns user_id if successful, None otherwise."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_current_user():
    """Get the currently logged in user ID from settings."""
    # This would be implemented to store session state
    # For now, return None (no user logged in)
    return None
