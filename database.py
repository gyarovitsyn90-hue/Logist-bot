import sqlite3

DB_NAME = "logistics.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            model TEXT,
            capacity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            client TEXT,
            address TEXT,
            vehicle_id INTEGER,
            status TEXT DEFAULT 'В работе',
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    """)

    conn.commit()
    conn.close()


def add_vehicle(number: str, model: str = None, capacity: int = 0):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO vehicles (number, model, capacity) VALUES (?, ?, ?)",
            (number, model, capacity)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_all_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, number, model, capacity FROM vehicles ORDER BY id")
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles


if __name__ == "__main__":
    init_db()
