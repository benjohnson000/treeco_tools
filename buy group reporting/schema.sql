PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sales_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document TEXT NOT NULL,
    invoice_type TEXT,
    account_number TEXT,
    customer_name TEXT,
    job TEXT,
    sales_material_branch TEXT,
    sale_date TEXT,
    accounting_year INTEGER,
    accounting_period INTEGER,
    item_ext_price NUMERIC,
    item_ext_cost NUMERIC,
    invoice_gm NUMERIC,
    item_number TEXT,
    item_description TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    unit_cost NUMERIC,
    item_gm NUMERIC,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sales_account ON sales_transactions(account_number);
CREATE INDEX IF NOT EXISTS idx_sales_item ON sales_transactions(item_number);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_transactions(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_branch ON sales_transactions(sales_material_branch);
