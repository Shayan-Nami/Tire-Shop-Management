from db_config import get_connection

def fetch_records(table_name, columns="*"):
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    columns_str = ", ".join(columns) if isinstance(columns, list) else columns
    sql = f"SELECT {columns_str} FROM {table_name}"
    try:
        cur.execute(sql)
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(dict(zip(colnames, row)))
        return result
    except Exception as e:
        print(f"An error occurred while fetching: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def create_record(table_name, columns, values):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    columns_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    try:
        cur.execute(sql, values)
        conn.commit()
        print(f"Record inserted into {table_name} successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def read_records(table_name):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    sql = f"SELECT * FROM {table_name}"
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        if rows:
            colnames = [desc[0] for desc in cur.description]
            print(f"\n--- Records from {table_name} ---")
            print(" | ".join(colnames))
            print("-" * (len(" | ".join(colnames)) + 20))
            for row in rows:
                print(" | ".join(map(str, row)))
            print("-" * (len(" | ".join(colnames)) + 20))
        else:
            print(f"No records found in {table_name}.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cur.close()
        conn.close()

def update_record(table_name, primary_key_column, primary_key_value, update_columns, new_values):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    set_clause = ", ".join([f"{col} = ?" for col in update_columns])
    sql = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key_column} = ?"
    values = new_values + [primary_key_value]
    try:
        cur.execute(sql, values)
        conn.commit()
        if cur.rowcount > 0:
            print(f"Record updated in {table_name} successfully!")
        else:
            print(f"No record found in {table_name} for {primary_key_column} = {primary_key_value}")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def delete_record(table_name, primary_key_column, primary_key_value):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    sql = f"DELETE FROM {table_name} WHERE {primary_key_column} = ?"
    try:
        cur.execute(sql, (primary_key_value,))
        conn.commit()
        if cur.rowcount > 0:
            print(f"Record deleted from {table_name} successfully!")
        else:
            print(f"No record found in {table_name} for {primary_key_column} = {primary_key_value}")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def create_full_purchase_invoice(supplier_id, invoice_date, items):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        sql_invoice = "INSERT INTO purchase_invoice (supplier_id, invoice_date, total_amount) OUTPUT inserted.purchase_invoice_id VALUES (?, ?, ?)"
        total_amount = sum(item['quantity'] * item['unit_cost'] for item in items)
        new_invoice_id = cur.execute(sql_invoice, (supplier_id, invoice_date, total_amount)).fetchval()
        sql_items = "INSERT INTO PurchaseInvoice_TireItems (purchaseinvoice_id, tire_id, quantity, unit_cost) VALUES (?, ?, ?, ?)"
        for item in items:
            cur.execute(sql_items, (new_invoice_id, item['tire_id'], item['quantity'], item['unit_cost']))
        sql_update_stock = "UPDATE tier SET stock_quantity = stock_quantity + ? WHERE tier_id = ?"
        for item in items:
            cur.execute(sql_update_stock, (item['quantity'], item['tire_id']))
        conn.commit()
        print(f"Purchase invoice #{new_invoice_id} created successfully!")
    except Exception as e:
        print(f"An error occurred. Transaction rolled back. Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def create_full_sales_invoice(customer_id, invoice_date, items):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        sql_invoice = "INSERT INTO sales_invoice (customer_id, invoice_date, total_amount) OUTPUT inserted.sales_invoice_id VALUES (?, ?, ?)"
        total_amount = sum(item['quantity'] * item['unit_price'] for item in items)
        new_invoice_id = cur.execute(sql_invoice, (customer_id, invoice_date, total_amount)).fetchval()
        sql_items = "INSERT INTO SalesInvoice_TireItems (salesinvoice_id, tire_id, quantity, unit_price) VALUES (?, ?, ?, ?)"
        for item in items:
            stock_check_cur = conn.cursor()
            stock_check_cur.execute("SELECT stock_quantity FROM tier WHERE tier_id = ?", item['tire_id'])
            current_stock = stock_check_cur.fetchval()
            if current_stock < item['quantity']:
                raise Exception(f"Not enough stock for tire ID {item['tire_id']}. Available: {current_stock}, Requested: {item['quantity']}")
            cur.execute(sql_items, (new_invoice_id, item['tire_id'], item['quantity'], item['unit_price']))
        sql_update_stock = "UPDATE tier SET stock_quantity = stock_quantity - ? WHERE tier_id = ?"
        for item in items:
            cur.execute(sql_update_stock, (item['quantity'], item['tire_id']))
        conn.commit()
        print(f"Sales invoice #{new_invoice_id} created successfully!")
    except Exception as e:
        print(f"An error occurred. Transaction rolled back. Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()