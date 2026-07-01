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
            pallets INTEGER DEFAULT 0,
            volume_m3 REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    """)

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN pallets INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN volume_m3 REAL DEFAULT 0")
    except:
        pass

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


def replace_all_vehicles(new_vehicles_list):
    """Полностью очищает таблицу машин и вставляет новые"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicles")
    added = 0
    for v in new_vehicles_list:
        try:
            cursor.execute("""
                INSERT INTO vehicles 
                (number, model, volume_m3, pallets, max_weight_kg, body_type, can_oversized, route_restrictions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, v)
            added += 1
        except:
            pass
    conn.commit()
    conn.close()
    return added


def bulk_add_orders_safe(orders_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    added, skipped = 0, 0
    skipped_reasons = []

    for order in orders_list:
        order_number, client, address, delivery_date, comment, pallets, volume_m3, vehicle_number = order
        vehicle = get_vehicle_by_number(vehicle_number)
        if not vehicle:
            skipped += 1
            skipped_reasons.append(f"{order_number} — машина {vehicle_number} не найдена")
            continue

        vehicle_id = vehicle[0]
        can_accept, reason = can_vehicle_accept_order(vehicle_id, pallets, volume_m3)
        if not can_accept:
            skipped += 1
            skipped_reasons.append(f"{order_number} — {reason}")
            continue

        try:
            cursor.execute("""
                INSERT INTO orders 
                (order_number, client, address, delivery_date, comment, pallets, volume_m3, vehicle_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'В работе')
            """, (order_number, client, address, delivery_date, comment, pallets, volume_m3, vehicle_id))
            added += 1
        except Exception:
            skipped += 1
            skipped_reasons.append(f"{order_number} — ошибка")

    conn.commit()
    conn.close()
    return added, skipped, skipped_reasons


def get_vehicle_by_number(vehicle_number):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, pallets, volume_m3 FROM vehicles WHERE number = ?", (vehicle_number,))
    vehicle = cursor.fetchone()
    conn.close()
    return vehicle


def can_vehicle_accept_order(vehicle_id, new_pallets, new_volume):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT pallets, volume_m3 FROM vehicles WHERE id = ?", (vehicle_id,))
    vehicle = cursor.fetchone()
    if not vehicle:
        return False, "Машина не найдена"

    max_pallets, max_volume = vehicle
    cursor.execute("""
        SELECT COALESCE(SUM(pallets), 0), COALESCE(SUM(volume_m3), 0)
        FROM orders WHERE vehicle_id = ?
    """, (vehicle_id,))
    current = cursor.fetchone()
    conn.close()

    current_pallets, current_volume = current
    if current_pallets + new_pallets > max_pallets:
        return False, f"Недостаточно паллет (занято {current_pallets}/{max_pallets})"
    if current_volume + new_volume > max_volume:
        return False, f"Недостаточно объёма"

    return True, "OK"


def get_all_vehicles():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, number, model, volume_m3, pallets FROM vehicles ORDER BY id")
    vehicles = cursor.fetchall()
    conn.close()
    return vehicles


def get_orders_by_date(target_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.client, o.address, o.delivery_date,
               o.status, o.comment, v.number, v.model, o.pallets, o.volume_m3
        FROM orders o
        LEFT JOIN vehicles v ON o.vehicle_id = v.id
        WHERE o.delivery_date = ?
        ORDER BY o.id
    """, (target_date,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def get_client_stats(client_name, start_date, end_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_orders,
            COALESCE(SUM(pallets), 0) as total_pallets,
            COALESCE(SUM(volume_m3), 0) as total_volume
        FROM orders 
        WHERE client LIKE ? 
          AND delivery_date BETWEEN ? AND ?
    """, (f"%{client_name}%", start_date, end_date))
    result = cursor.fetchone()
    conn.close()
    return result


def get_client_orders(client_name, start_date, end_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.order_number, o.client, o.address, o.delivery_date,
               o.status, o.comment, o.pallets, o.volume_m3,
               v.number, v.model
        FROM orders o
        LEFT JOIN vehicles v ON o.vehicle_id = v.id
        WHERE o.client LIKE ? 
          AND o.delivery_date BETWEEN ? AND ?
        ORDER BY o.delivery_date
    """, (f"%{client_name}%", start_date, end_date))
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


def update_order_vehicle(order_id, new_vehicle_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET vehicle_id = ? WHERE id = ?", (new_vehicle_id, order_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated > 0
