from crud_operations import create_record, read_records, update_record, delete_record, fetch_records

tables = [
    "customer", "brand", "size", "tier", "supplier", "services",
    "sales_invoice", "purchase_invoice", "receipt_voucher", "Payment_voucher",
]

primary_keys = {
    'customer': 'customer_id',
    'brand': 'brand_id',
    'size': 'size_id',
    'tier': 'tier_id',
    'supplier': 'supplier_id',
    'services': 'service_id',
    'sales_invoice': 'sales_invoice_id',
    'purchase_invoice': 'purchase_invoice_id',
    'receipt_voucher': 'receipt_id',
    'payment_voucher': 'payment_id',
}

insertable_columns = {
    'customer': ['full_name', 'phone_number', 'national_code', 'address'],
    'brand': ['brand_name'],
    'size': ['size_name'],
    'tier': ['tier_name', 'stock_quantity', 'sale_price', 'purchase_price', 'brand_id', 'size_id'],
    'supplier': ['supplier_name', 'phone_number', 'address'],
    'services': ['service_name', 'price'],
    'receipt_voucher': ['receipt_date', 'amount', 'sales_invoice_id'],
    'Payment_voucher': ['payment_date', 'amount', 'purchase_invoice_id'],
}

display_column_map = {
    'customer': 'full_name',
    'brand': 'brand_name',
    'size': 'size_name',
    'tier': 'tier_name',
    'supplier': 'supplier_name',
    'services': 'service_name',
    'sales_invoice': 'sales_invoice_id',
    'purchase_invoice': 'purchase_invoice_id',
}

def get_table_choice():
    print("\n--- Available Tables ---")
    for idx, table in enumerate(tables, start=1):
        print(f"{idx}. {table}")
    while True:
        try:
            choice = int(input("Select a table by number: "))
            if 1 <= choice <= len(tables):
                return tables[choice - 1]
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_record_for_action(table_name, pk_column):
    print(f"\n--- Select a record from '{table_name}' to perform the action ---")
    display_col = display_column_map.get(table_name, pk_column)
    try:
        records = fetch_records(table_name, columns=[pk_column, display_col])
    except Exception:
        records = fetch_records(table_name)
        if not records:
            print(f"No records found in '{table_name}'.")
            return None
        if len(records[0].keys()) > 1:
            display_col = list(records[0].keys())[1]
        else:
            display_col = pk_column
    if not records:
        print(f"No records found in '{table_name}'.")
        return None
    for idx, record in enumerate(records, start=1):
        print(f"{idx}. {record.get(display_col, 'N/A')} (ID: {record[pk_column]})")
    while True:
        try:
            choice = int(input("Select a record by number: "))
            if 1 <= choice <= len(records):
                return records[choice - 1][pk_column]
            else:
                print("Invalid number.")
        except (ValueError, KeyError):
            print("Invalid input. Please enter a number.")

def get_value_from_user(column_name):
    if column_name.endswith('_id'):
        ref_table = column_name.replace('_id', '')
        pk_col_for_ref = primary_keys.get(ref_table, column_name)
        selected_id = select_record_for_action(ref_table, pk_col_for_ref)
        return selected_id
    else:
        return input(f"Enter value for '{column_name}': ")

def create_purchase_invoice_interactive():
    print("\n--- Creating a New Purchase Invoice ---")
    invoice_date = input("Enter invoice date (YYYY-MM-DD): ")
    supplier_id = select_record_for_action('supplier', 'supplier_id')
    if not supplier_id:
        print("Supplier selection cancelled.")
        return
    items_to_purchase = []
    while True:
        print("\n--- Add a Tire to the Invoice ---")
        tire_id = select_record_for_action('tier', 'tier_id')
        if not tire_id:
            break
        try:
            quantity = int(input("Enter quantity: "))
            unit_cost = float(input("Enter unit cost (purchase price): "))
        except ValueError:
            print("Invalid number. Please try again.")
            continue
        items_to_purchase.append({
            'tire_id': tire_id,
            'quantity': quantity,
            'unit_cost': unit_cost
        })
        add_more = input("Add another tire to this invoice? (yes/no): ").lower()
        if add_more != 'yes':
            break
    if not items_to_purchase:
        print("No items added. Invoice creation cancelled.")
        return
    from crud_operations import create_full_purchase_invoice
    create_full_purchase_invoice(supplier_id, invoice_date, items_to_purchase)

def create_sales_invoice_interactive():
    print("\n--- Creating a New Sales Invoice ---")
    invoice_date = input("Enter invoice date (YYYY-MM-DD): ")
    customer_id = select_record_for_action('customer', 'customer_id')
    if not customer_id:
        print("Customer selection cancelled.")
        return
    items_to_sell = []
    while True:
        print("\n--- Add a Tire to the Invoice ---")
        tire_id = select_record_for_action('tier', 'tier_id')
        if not tire_id:
            break
        try:
            quantity = int(input("Enter quantity: "))
            unit_price = float(input("Enter unit price (sale price): "))
        except ValueError:
            print("Invalid number. Please try again.")
            continue
        items_to_sell.append({
            'tire_id': tire_id,
            'quantity': quantity,
            'unit_price': unit_price
        })
        add_more = input("Add another tire to this invoice? (yes/no): ").lower()
        if add_more != 'yes':
            break
    if not items_to_sell:
        print("No items added. Invoice creation cancelled.")
        return
    from crud_operations import create_full_sales_invoice
    create_full_sales_invoice(customer_id, invoice_date, items_to_sell)

def main():
    while True:
        table_name = get_table_choice()
        pk_column = primary_keys.get(table_name)
        is_simple_pk = pk_column and ',' not in pk_column
        print(f"\nSelected Table: {table_name}")
        print("--- Available Operations ---")
        print("1. Create a new record")
        print("2. Read all records")
        print("3. Update a record")
        print("4. Delete a record")
        print("5. Choose another table")
        print("6. Exit")
        try:
            operation = int(input("Select an operation by number: "))
        except ValueError:
            print("Invalid input. Please select a number.")
            continue
        if operation == 1:
            if table_name == 'purchase_invoice':
                create_purchase_invoice_interactive()
                continue
            elif table_name == 'sales_invoice':
                create_sales_invoice_interactive()
                continue
            columns = insertable_columns.get(table_name)
            if not columns:
                print(f"Create operation is not configured for table '{table_name}' in this script.")
                continue
            values = []
            print("\nPlease provide values for the following columns:")
            for col in columns:
                value = get_value_from_user(col)
                if value is None:
                    break
                values.append(value)
            if len(values) == len(columns):
                create_record(table_name, columns, values)
        elif operation == 2:
            read_records(table_name)
        elif operation == 3:
            if not is_simple_pk:
                print("Update operation is not supported for tables with composite keys.")
                continue
            pk_value = select_record_for_action(table_name, pk_column)
            if pk_value is None:
                continue
            print(f"\nUpdating record with {pk_column} = {pk_value}")
            update_cols_input = input("Enter column(s) to update (comma-separated): ")
            update_cols = [col.strip() for col in update_cols_input.split(",")]
            new_vals_input = input(f"Enter new values for [{', '.join(update_cols)}] (comma-separated): ")
            new_vals = [val.strip() for val in new_vals_input.split(",")]
            update_record(table_name, pk_column, pk_value, update_cols, new_vals)
        elif operation == 4:
            if not is_simple_pk:
                print("Delete operation is not supported for tables with composite keys.")
                continue
            pk_value = select_record_for_action(table_name, pk_column)
            if pk_value is None:
                continue
            confirmation = input(
                f"Are you sure you want to delete the record with {pk_column} = {pk_value}? (yes/no): ")
            if confirmation.lower() == 'yes':
                delete_record(table_name, pk_column, pk_value)
            else:
                print("Deletion cancelled.")
        elif operation == 5:
            continue
        elif operation == 6:
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid operation selected.")

if __name__ == '__main__':
    main()