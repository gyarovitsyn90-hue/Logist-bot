import sqlite3

DB_NAME = "logistics.db"

MACHINES = [
    ("Е830ЕТ799", "Ивеко Дейли", 30, 12, 3500, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Категория: Средняя", 1),
    ("К236СН777", "DAF FT XF 105", 82, 33, 30000, "тент", 1, None, None, "Тип кузова: тент | Негабарит: Да | Маршруты: основная перевозка Лемана Про(леруа мерлен) | Категория: Крупнотоннажная", 1),
    ("К786УА799", "Пежо Боксер", 8, 4, 1800, "фургон", 1, None, None, "Тип кузова: фургон | Негабарит: Да | Маршруты: маленькая машина удобно по городу | Категория: Малая", 1),
    ("С119МТ777", "Ивеко Дейли", 30, 12, 3500, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Категория: Средняя", 1),
    ("С236ХУ799", "Пежо партнер", 3, 1, 700, "фургон", 1, None, None, "Тип кузова: фургон | Негабарит: Да | Маршруты: маленькая машина удобно по городу | Категория: Малая", 1),
    ("С741ХУ799", "Пежо боксер", 8, 4, 1400, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Маршруты: маленькая машина удобно по городу | Категория: Малая", 1),
    ("Т176НМ777", "Ивеко EURO CARGO", 50, 24, 6500, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Маршруты: не удобно заезжать в москву. | Категория: Большая", 1),
    ("Т417СО797", "Донг фенг", 16, 8, 4000, "тент", 1, None, None, "Тип кузова: тент | Негабарит: Да | Категория: Средняя", 1),
    ("Т530ХА799", "DAF LF-210", 40, 18, 5000, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Маршруты: не удобно заезжать в москву,дополнительно перевозка Лемана Про(леруа мерлен). | Категория: Большая", 1),
    ("У289РХ797", "Донг Фенг", 75, 18, 7500, "тент", 1, None, None, "Тип кузова: тент | Негабарит: Да | Категория: Большая", 1),
    ("У885АУ777", "Ивеко Дейли", 26, 10, 3000, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Категория: Средняя", 1),
    ("Х794ХЕ799", "Ивеко дейли", 26, 10, 3000, "будка", 1, None, None, "Тип кузова: будка | Негабарит: Да | Категория: Средняя", 1),
]

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
            is_active INTEGER DEFAULT 1
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Автоматически добавляем машины, если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM vehicles")
    if cursor.fetchone()[0] == 0:
        for m in MACHINES:
            try:
                cursor.execute("""
                    INSERT INTO vehicles 
                    (number, model, volume_m3, pallets, max_weight_kg, body_type, 
                     can_oversized, allowed_routes, forbidden_routes, restrictions, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, m)
            except:
                pass

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
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_active_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE is_active = 1")
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles


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
