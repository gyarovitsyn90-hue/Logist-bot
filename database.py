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
            volume_m3 REAL DEFAULT 0,
            pallets INTEGER DEFAULT 0,
            max_weight_kg INTEGER DEFAULT 0,
            body_type TEXT,
            can_oversized INTEGER DEFAULT 0,
            allowed_routes TEXT,
            forbidden_routes TEXT,
            restrictions TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def replace_all_vehicles(vehicles_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicles")

    added = 0
    for v in vehicles_list:
        try:
            cursor.execute("""
                INSERT INTO vehicles 
                (number, model, volume_m3, pallets, max_weight_kg, body_type, 
                 can_oversized, allowed_routes, forbidden_routes, restrictions, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, v)
            added += 1
        except Exception as e:
            print(f"Ошибка добавления машины: {e}")

    conn.commit()
    conn.close()
    return added


def get_active_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE is_active = 1")
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles


def get_all_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles ORDER BY id")
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles
