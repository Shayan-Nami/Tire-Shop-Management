# Tire Shop Management System 🛞

![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat&logo=python)
![SQL Server](https://img.shields.io/badge/Database-SQL%20Server-red?style=flat&logo=microsoftsqlserver)

---

## 📘 Overview
This project is a comprehensive **Database Management System (DBMS)** designed for managing a tire shop’s operations — including customers, sales, purchases, inventory tracking, and reporting.

---

## 📂 Project Structure

The project follows a phased development structure, separating documentation from implementation:

```text
Tire-Shop-Management/
│
├── Phase 1 & 2 (Design & Docs)
│   ├── Untitled Diagram.jpg        # Entity-Relationship Diagram (ERD)
│   └── Documentation.pdf           # Full academic report and scenarios
│
├── Phase 3 (Implementation)
│   ├── Queries.txt                 # SQL DDL/DML scripts for Schema creation
│   │
│   ├── crud/                       # CORE LOGIC: Data Manipulation
│   │   ├── main.py                 # CLI Entry point for Admin operations
│   │   ├── crud_operations.py      # Python functions for SQL execution
│   │   └── db_config.py            # Database connection settings
│   │
│   └── report/                     # ANALYTICS: Business Intelligence
│       ├── run_reports.py          # Entry point for Report generation
│       └── report_generator.py     # SQL Aggregation logic for insights
│
└── README.md                       # Project Documentation
```

### Phase Summary:
- **Phase 1 & 2 (Documentation):**
  - Includes the **ER Diagram** (`Untitled Diagram.jpg`)
  - Full project documentation and use-case scenarios (`PDF file`)

- **Phase 3 (Implementation):**
  - **crud/** → Contains the main application logic for managing data (Create, Read, Update, Delete)
  - **report/** → Contains scripts for generating financial and inventory reports
  - **Queries.txt** → SQL commands used to create tables and views

---

## ⚙️ Features

### 🗂 Data Management (CRUD)
- Manage **Customers**, **Tires**, **Brands**, and **Suppliers**  

### 💳 Transactions
- Process **Sales** and **Purchase** invoices  

### 📊 Reporting System
- Sales by Brand  
- Profitability Analysis  
- Inventory Value Calculation  
- Low Stock Alerts  

---

## 🧩 Prerequisites
- **Python 3.x**  
- **Microsoft SQL Server**  
- **Driver:** ODBC Driver 17 for SQL Server  

---

## 🚀 How to Run

### 1️⃣ Setup Database
Create a database named `TireShopDB` and run the scripts in `Queries.txt`.

### 2️⃣ Install Dependencies
```bash
pip install pyodbc
```

### 3️⃣ Run App

#### To manage data (CRUD):
```bash
cd "Phase 3/crud"
python main.py
```

#### To generate reports:
```bash
cd "Phase 3/report"
python run_reports.py
```

---

## 👤 Author
**Shayan Abdollahi Nami**

---







