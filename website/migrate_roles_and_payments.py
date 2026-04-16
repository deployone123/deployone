import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    # Use 'deployone' as the database name, which is what app.py uses
    return pymysql.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'admin'),
        password=os.environ.get('DB_PASS', 'alumnat'),
        database=os.environ.get('DB_NAME', 'deployone'),
        cursorclass=pymysql.cursors.DictCursor
    )

def migrate():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            print("Starting migration...")
            
            # 1. Update users table: change default role to 'free'
            # Check if role column exists and its current default
            cursor.execute("DESCRIBE users")
            columns = cursor.fetchall()
            role_col = next((c for c in columns if c['Field'] == 'role'), None)
            
            if role_col:
                print("Updating users table role default...")
                cursor.execute("ALTER TABLE users MODIFY COLUMN role VARCHAR(50) NOT NULL DEFAULT 'free'")
                # Also update existing 'user' roles to 'free' if requested? 
                # Let's just update all non-admins to 'free' to be safe for this new system
                cursor.execute("UPDATE users SET role = 'free' WHERE role = 'user'")
            
            # 2. Create purchased_playbooks table
            print("Creating purchased_playbooks table...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchased_playbooks (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                playbook_path VARCHAR(255) NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY user_playbook (user_id, playbook_path)
            ) ENGINE=InnoDB
            ''')

            # 3. Create free_trial_usage table
            print("Creating free_trial_usage table...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS free_trial_usage (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                playbook_path VARCHAR(255) NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY user_playbook_trial (user_id, playbook_path)
            ) ENGINE=InnoDB
            ''')
            
            conn.commit()
            print("Migration successful.")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
