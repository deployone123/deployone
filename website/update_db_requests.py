import pymysql
import os
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

def update_db_for_requests():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Create deployment_requests table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                playbook_names TEXT NOT NULL,  -- Stored as a comma-separated string or JSON
                status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'denied', 'deployed'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
            conn.commit()
            print("Database updated with deployment_requests table.")
    finally:
        conn.close()

if __name__ == '__main__':
    update_db_for_requests()
