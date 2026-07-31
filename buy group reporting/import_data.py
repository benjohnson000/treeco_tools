"""Import sales history and account/buy-group mappings into SQLite."""

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    row_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS buy_groups (
    account_key TEXT PRIMARY KEY,
    account_number TEXT NOT NULL,
    buy_group TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
    document TEXT NOT NULL,
    invoice_type TEXT,
    account_number TEXT NOT NULL,
    customer_name TEXT,
    job TEXT,
    sales_material_branch TEXT,
    sale_date TEXT,
    accounting_year INTEGER,
    accounting_period INTEGER,
    item_ext_price REAL,
    item_ext_cost REAL,
    invoice_gm REAL,
    item TEXT,
    description TEXT,
    quantity REAL,
    unit_price REAL,
    unit_cost REAL,
    item_gm REAL
);

CREATE INDEX IF NOT EXISTS idx_sales_account ON sales(account_number);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_batch ON sales(import_batch_id);
"""


def clean(value):
    return value.strip() if value is not None else ""


def number(value, kind=float):
    value = clean(value)
    return None if value == "" else kind(value)


def account_key(value):
    value = clean(value)
    return value if "~" in value else f"{value}~0"


def parse_date(value):
    value = clean(value)
    if not value:
        return None
    return datetime.strptime(value, "%m/%d/%Y %H:%M:%S").date().isoformat()


def import_buy_groups(connection, path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            group = clean(row["Buy Group"]) or "Unassigned"
            account = clean(row["Account Number"])
            if account:
                rows.append((account_key(account), account.split("~", 1)[0], group))
    connection.executemany(
        "INSERT OR REPLACE INTO buy_groups(account_key, account_number, buy_group) VALUES (?, ?, ?)",
        rows,
    )
    return len(rows)


def import_sales(connection, path):
    columns = (
        "document, invoice_type, account_number, customer_name, job, sales_material_branch,"
        "sale_date, accounting_year, accounting_period, item_ext_price, item_ext_cost, invoice_gm,"
        "item, description, quantity, unit_price, unit_cost, item_gm"
    )
    sql = f"INSERT INTO sales(import_batch_id, {columns}) VALUES (?, {','.join(['?'] * 18)})"
    imported_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append((
                clean(row["Document"]), clean(row["Inv Type"]), clean(row["Account"]),
                clean(row["Name"]), clean(row["Job"]), clean(row["Sales/ Material Branch"]),
                parse_date(row["Date"]), number(row["Accounting Year"], int),
                number(row["Accounting Period"], int), number(row["Item Ext Price"]),
                number(row["Item Ext Cost"]), number(row["Invoice GM"]), clean(row["Item"]),
                clean(row["Description"]), number(row["Quantity"]), number(row["Unit Price"]),
                number(row["Unitcost"]), number(row["Item GM"]),
            ))
    cursor = connection.execute(
        "INSERT INTO import_batches(source_file, imported_at, row_count) VALUES (?, ?, ?)",
        (str(path), imported_at, len(rows)),
    )
    batch_id = cursor.lastrowid
    connection.executemany(sql, [(batch_id, *row) for row in rows])
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sales_csv", type=Path)
    parser.add_argument("buy_groups_csv", type=Path)
    parser.add_argument("--database", type=Path, default=Path("buy_group_reporting.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.database) as connection:
        connection.executescript(SCHEMA)
        groups = import_buy_groups(connection, args.buy_groups_csv)
        sales = import_sales(connection, args.sales_csv)
    print(f"Imported {sales:,} sales rows and {groups:,} buy-group mappings into {args.database}")


if __name__ == "__main__":
    main()
