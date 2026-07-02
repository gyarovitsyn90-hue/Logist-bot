import sqlite3

DB_NAME = "logistics.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица машин
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
            is_active INTEGER DEFAULT 1
        )
    """)

    # Таблица заказов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            client TEXT,
            address TEXT,
            delivery_date TEXT,
            vehicle_id INTEGER,
            status TEXT DEFAULT 'Не распределён',
            comment TEXT,
            pallets INTEGER DEFAULT 0,
            volume_m3 REAL DEFAULT 0
        )
    """)

    # Таблица настроек (для конечной точки)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value) 
        VALUES (?, ?)
    """, (key, value))
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
        except:
            pass

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
