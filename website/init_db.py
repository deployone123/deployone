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
            # Disable foreign key checks to prevent initialization errors
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                client_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'client',
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            ''')

            # Create machines table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                machine_id INT AUTO_INCREMENT PRIMARY KEY,
                proxmox_vmid INT UNIQUE NOT NULL,
                machine_name VARCHAR(100),
                machine_type ENUM('lxc', 'qemu') DEFAULT 'lxc',
                internal_ip VARCHAR(15),
                owner_id INT,
                FOREIGN KEY (owner_id) REFERENCES users (client_id) ON DELETE SET NULL
            ) ENGINE=InnoDB
            ''')

            # Create deployment_requests table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_requests (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                playbook_names TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (client_id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            ''')

            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()

            # Add admin user if it doesn't exist
            cursor.execute("SELECT client_id FROM users WHERE username = %s", ('admin',))
            if not cursor.fetchone():
                admin_pass = generate_password_hash('alumnat')
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                               ('admin', admin_pass, 'admin'))

            # Add a test user
            cursor.execute("SELECT client_id FROM users WHERE username = %s", ('test',))
            if not cursor.fetchone():
                test_pass = generate_password_hash('test')
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                               ('test', test_pass, 'user'))

            conn.commit()

            # Get user IDs
            cursor.execute("SELECT client_id FROM users WHERE username = %s", ('admin',))
            admin_id = cursor.fetchone()['client_id']
            cursor.execute("SELECT client_id FROM users WHERE username = %s", ('test',))
            test_id = cursor.fetchone()['client_id']

            # Add some sample machines (using the actual column names)
            cursor.execute("SELECT machine_id FROM machines WHERE machine_name = %s", ('Admin-VM-1',))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO machines (proxmox_vmid, machine_name, internal_ip, owner_id) VALUES (%s, %s, %s, %s)",
                               (1001, 'Admin-VM-1', '10.20.0.242', admin_id))
            
            cursor.execute("SELECT machine_id FROM machines WHERE machine_name = %s", ('Test-VM-1',))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO machines (proxmox_vmid, machine_name, internal_ip, owner_id) VALUES (%s, %s, %s, %s)",
                               (1002, 'Test-VM-1', '10.20.0.10', test_id))

            conn.commit()
            print("Database initialized successfully.")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
