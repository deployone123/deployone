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

def add_unassigned_machine():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Add an unassigned machine
            cursor.execute("SELECT id FROM machines WHERE name = %s", ('Cloud-VM-Unassigned',))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (%s, %s, %s, %s)",
                               ('Cloud-VM-Unassigned', '100.121.99.42', 7683, None))
                conn.commit()
                print("Unassigned machine added.")
            else:
                print("Machine already exists.")
    finally:
        conn.close()

if __name__ == '__main__':
    add_unassigned_machine()
