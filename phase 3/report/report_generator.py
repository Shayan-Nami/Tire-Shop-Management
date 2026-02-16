import db_config
from datetime import datetime

def fetch_brands_list():
    conn = db_config.get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        query = "SELECT brand_id, brand_name FROM Brand ORDER BY brand_name"
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results
    finally:
        if conn:
            conn.close()

def generate_sales_by_brand_report(brand_id):
    print(f"\nGenerating sales report for brand ID: {brand_id}...")
    query = """
    SELECT
        B.brand_name, T.tier_name, SI.sales_invoice_id,
        SI.invoice_date, C.full_name AS customer_name
    FROM Brand AS B
    JOIN Tier AS T ON B.brand_id = T.brand_id
    JOIN SalesInvoice_TireItems AS SIT ON T.tier_id = SIT.tire_id
    JOIN Sales_invoice AS SI ON SIT.salesinvoice_id = SI.sales_invoice_id
    JOIN Customer AS C ON SI.customer_id = C.customer_id
    WHERE B.brand_id = ?
    ORDER BY SI.invoice_date DESC;
    """
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query, brand_id)
        results = cursor.fetchall()
        if not results:
            return f"No sales records found for brand ID {brand_id}."
        brand_name = results[0][0]
        report_lines = [f"--- Sales Report for Brand: {brand_name} ---"]
        for row in results:
            invoice_date = row[3].strftime('%Y-%m-%d')
            report_lines.append(
                f"Tire: {row[1]} | "
                f"Sold to: {row[4]} | "
                f"Invoice #{row[2]} on {invoice_date}"
            )
        return "\n".join(report_lines)
    finally:
        if conn:
            conn.close()

def generate_sales_summary_report():
    print("\nGenerating Sales Summary Report...")
    query = "SELECT COUNT(DISTINCT salesinvoice_id), SUM(quantity * unit_price) FROM SalesInvoice_TireItems;"
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        if not result or result[0] is None or result[0] == 0:
            return "No sales data available."
        total_invoices = result[0]
        total_revenue = result[1]
        report = (
            f"--- Sales Summary Report ---\n"
            f"Total Invoices: {int(total_invoices)}\n"
            f"Total Revenue from Tires: {total_revenue:,.2f}"
        )
        return report
    finally:
        if conn:
            conn.close()

def generate_profitability_report():
    print("\nGenerating Tire Profitability Report...")
    query = """
    SELECT
        T.tier_name,
        SUM(SIT.quantity) AS total_sold,
        SUM(SIT.quantity * (T.sale_price - T.purchase_price)) AS total_profit
    FROM Tier AS T
    JOIN SalesInvoice_TireItems AS SIT ON T.tier_id = SIT.tire_id
    WHERE T.purchase_price > 0
    GROUP BY T.tier_name
    ORDER BY total_profit DESC;
    """
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        if not results:
            return "No sales data available to calculate profitability."
        report_lines = ["--- Tire Profitability Report ---"]
        for row in results:
            report_lines.append(
                f"Tire: {row[0]} | "
                f"Total Sold: {int(row[1])} | "
                f"Total Profit: {row[2]:,.2f}"
            )
        return "\n".join(report_lines)
    finally:
        if conn:
            conn.close()

def generate_inventory_value_report():
    print("\nGenerating Inventory Value Report...")
    query = """
    SELECT
        tier_name, stock_quantity,
        (stock_quantity * purchase_price) AS inventory_value
    FROM Tier
    WHERE stock_quantity > 0
    ORDER BY inventory_value DESC;
    """
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        if not results:
            return "No inventory found."
        report_lines = ["--- Inventory Value Report (based on Purchase Price) ---"]
        total_inventory_value = 0
        for row in results:
            inventory_value = row[2]
            report_lines.append(
                f"Tire: {row[0]} | "
                f"Stock: {row[1]} | "
                f"Value: {inventory_value:,.2f}"
            )
            total_inventory_value += inventory_value
        report_lines.append("\n" + "="*40)
        report_lines.append(f"TOTAL INVENTORY VALUE: {total_inventory_value:,.2f}")
        return "\n".join(report_lines)
    finally:
        if conn:
            conn.close()

def generate_sales_by_date_range_report(start_date, end_date):
    print(f"\nGenerating sales report from {start_date} to {end_date}...")
    query = """
    SELECT
        SI.invoice_date,
        C.full_name AS customer_name,
        T.tier_name,
        SIT.quantity
    FROM Sales_invoice AS SI
    JOIN Customer AS C ON SI.customer_id = C.customer_id
    JOIN SalesInvoice_TireItems AS SIT ON SI.sales_invoice_id = SIT.salesinvoice_id
    JOIN Tier AS T ON SIT.tire_id = T.tier_id
    WHERE SI.invoice_date BETWEEN ? AND ?
    ORDER BY SI.invoice_date;
    """
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query, start_date, end_date)
        results = cursor.fetchall()
        if not results:
            return f"No sales records found between {start_date} and {end_date}."
        report_lines = [f"--- Sales Report: {start_date} to {end_date} ---"]
        for row in results:
            sale_date = row[0].strftime('%Y-%m-%d')
            customer = row[1]
            tire_name = row[2]
            quantity = row[3]
            report_lines.append(
                f"Date: {sale_date} | Customer: {customer} | Tire: {tire_name} | Quantity: {int(quantity)}"
            )
        return "\n".join(report_lines)
    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()

def generate_remaining_stock_report():
    print("\nGenerating Remaining Stock Report...")
    query = """
    SELECT
        T.tier_name,
        T.stock_quantity,
        B.brand_name,
        S.size_name,
        T.brand_id,
        T.size_id
    FROM Tier AS T
    JOIN Brand AS B ON T.brand_id = B.brand_id
    JOIN Size AS S ON T.size_id = S.size_id
    WHERE T.stock_quantity > 0
    ORDER BY B.brand_name, T.tier_name;
    """
    conn = db_config.get_connection()
    if not conn:
        return "Could not connect to the database."
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        if not results:
            return "No stock found."
        report_lines = ["--- Remaining Tire Stock Report ---"]
        for row in results:
            report_lines.append(
                f"Tire: {row[0]} | "
                f"Stock: {row[1]} | "
                f"Brand: {row[2]} (ID: {row[4]}) | "
                f"Size: {row[3]} (ID: {row[5]})"
            )
        return "\n".join(report_lines)
    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()