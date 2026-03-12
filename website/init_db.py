import pymysql
import os
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'admin'),
        password=os.environ.get('DB_PASS', 'alumnat'),
        database=os.environ.get('DB_NAME', 'website'),
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user'
            )
            ''')

            # Create machines table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                ip VARCHAR(255) NOT NULL,
                ttyd_port INT NOT NULL DEFAULT 7681,
                owner_id INT,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            )
            ''')

            # Create deployment_requests table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                playbook_names TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Add admin user if it doesn't exist
            cursor.execute("SELECT id FROM users WHERE username = %s", ('admin',))
            if not cursor.fetchone():
                admin_pass = generate_password_hash('alumnat')
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                               ('admin', admin_pass, 'admin'))

            # Add a test user
            cursor.execute("SELECT id FROM users WHERE username = %s", ('test',))
            if not cursor.fetchone():
                test_pass = generate_password_hash('test')
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                               ('test', test_pass, 'user'))

            conn.commit()

            # Get user IDs
            cursor.execute("SELECT id FROM users WHERE username = %s", ('admin',))
            admin_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM users WHERE username = %s", ('test',))
            test_id = cursor.fetchone()['id']

            # Add some sample machines
            cursor.execute("SELECT id FROM machines WHERE name = %s", ('Admin-VM-1',))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (%s, %s, %s, %s)",
                               ('Admin-VM-1', '100.121.99.42', 7681, admin_id))
            
            cursor.execute("SELECT id FROM machines WHERE name = %s", ('Test-VM-1',))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (%s, %s, %s, %s)",
                               ('Test-VM-1', '100.121.99.42', 7682, test_id))

            conn.commit()
            print("Database initialized successfully.")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
