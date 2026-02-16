import report_generator
from datetime import datetime

def select_from_list(items, id_key, display_key):
    if not items:
        print("No items to display.")
        return None
    for idx, item in enumerate(items, start=1):
        print(f"{idx}. {item[display_key]} (ID: {item[id_key]})")
    while True:
        try:
            choice = int(input("Select by number: "))
            if 1 <= choice <= len(items):
                return items[choice - 1][id_key]
            else:
                print("Invalid number.")
        except (ValueError, KeyError):
            print("Invalid input. Please enter a number.")

def main():
    print("Welcome to the Business Reports System")
    while True:
        print("\nSelect the report you want to generate:")
        print("1. Sales Report by Brand")
        print("2. Sales Summary Report")
        print("3. Tire Profitability Report")
        print("4. Inventory Value Report")
        print("5. Sales Report by Date Range")
        print("6. Remaining Stock Report")
        print("7. Exit")
        choice = input("Enter your choice (1-7): ")
        if choice == '1':
            print("\n--- Select a Brand ---")
            brands_list = report_generator.fetch_brands_list()
            brand_id = select_from_list(brands_list, 'brand_id', 'brand_name')
            if brand_id:
                report = report_generator.generate_sales_by_brand_report(brand_id)
                print("\n" + report)
        elif choice == '2':
            report = report_generator.generate_sales_summary_report()
            print("\n" + report)
        elif choice == '3':
            report = report_generator.generate_profitability_report()
            print("\n" + report)
        elif choice == '4':
            report = report_generator.generate_inventory_value_report()
            print("\n" + report)
        elif choice == '5':
            print("\n--- Generate Report by Date Range ---")
            start_date_str = input("Enter start date (YYYY-MM-DD): ")
            end_date_str = input("Enter end date (YYYY-MM-DD): ")
            try:
                datetime.strptime(start_date_str, '%Y-%m-%d')
                datetime.strptime(end_date_str, '%Y-%m-%d')
                report = report_generator.generate_sales_by_date_range_report(start_date_str, end_date_str)
                print("\n" + report)
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        elif choice == '6':
            report = report_generator.generate_remaining_stock_report()
            print("\n" + report)
        elif choice == '7':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == '__main__':
    main()