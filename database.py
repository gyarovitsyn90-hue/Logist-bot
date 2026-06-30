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
            route_restrictions TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            status TEXT DEFAULT 'В работе',
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    """)

    conn.commit()
    conn.close()


def add_vehicle(number, model=None, volume_m3=0, pallets=0, max_weight_kg=0,
                body_type=None, can_oversized=0, route_restrictions=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO vehicles 
            (number, model, volume_m3, pallets, max_weight_kg, body_type, can_oversized, route_restrictions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (number, model, volume_m3, pallets, max_weight_kg, body_type, can_oversized, route_restrictions))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def bulk_add_vehicles(vehicles_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    added, skipped = 0, 0

    for v in vehicles_list:
        try:
            cursor.execute("""
                INSERT INTO vehicles 
                (number, model, volume_m3, pallets, max_weight_kg, body_type, can_oversized, route_restrictions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, v)
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    conn.close()
    return added, skipped


def bulk_add_orders(orders_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    added, skipped = 0, 0

    for order in orders_list:
        try:
            cursor.execute("""
                INSERT INTO orders 
                (order_number, client, address, delivery_date, comment, status)
                VALUES (?, ?, ?, ?, ?, 'В работе')
            """, order)
            added += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()
    return added, skipped


def get_all_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, number, model, volume_m3, pallets, max_weight_kg, body_type 
        FROM vehicles ORDER BY id
    """)
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles


def get_orders_by_date(target_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.client, o.address, o.delivery_date,
               o.status, o.comment, v.number, v.model
        FROM orders o
        LEFT JOIN vehicles v ON o.vehicle_id = v.id
        WHERE o.delivery_date = ?
        ORDER BY o.id
    """, (target_date,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def delete_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted > 0
