import sqlite3

def update_db_for_requests():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create deployment_requests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deployment_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        playbook_names TEXT NOT NULL,  -- Stored as a comma-separated string or JSON
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'denied', 'deployed'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database updated with deployment_requests table.")

if __name__ == '__main__':
    update_db_for_requests()
