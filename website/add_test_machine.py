import sqlite3

def add_unassigned_machine():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Add an unassigned machine
    cursor.execute("SELECT id FROM machines WHERE name = 'Cloud-VM-Unassigned'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO machines (name, ip, ttyd_port, owner_id) VALUES (?, ?, ?, ?)",
                       ('Cloud-VM-Unassigned', '100.121.99.42', 7683, None))
        print("Unassigned machine added.")
    else:
        print("Machine already exists.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_unassigned_machine()
