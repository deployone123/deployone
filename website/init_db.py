import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    ''')

    # Create machines table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ip TEXT NOT NULL,
        ttyd_port INTEGER NOT NULL DEFAULT 7681,
        owner_id INTEGER,
        FOREIGN KEY (owner_id) REFERENCES users (id)
    )
    ''')

    # Add admin user if it doesn't exist
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_pass = generate_password_hash('alumnat')
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                       ('admin', admin_pass, 'admin'))

    # Add a test user
    cursor.execute("SELECT id FROM users WHERE username = 'test'")
    if not cursor.fetchone():
        test_pass = generate_password_hash('test')
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                       ('test', test_pass, 'user'))

    # Get user IDs
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    admin_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM users WHERE username = 'test'")
    test_id = cursor.fetchone()[0]

    # Add some sample machines
    cursor.execute("SELECT id FROM machines WHERE name = 'Admin-VM-1'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (?, ?, ?, ?)",
                       ('Admin-VM-1', '100.121.99.42', 7681, admin_id))
    
    cursor.execute("SELECT id FROM machines WHERE name = 'Test-VM-1'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (?, ?, ?, ?)",
                       ('Test-VM-1', '100.121.99.42', 7682, test_id))

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
