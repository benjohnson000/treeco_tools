"""Import a sales CSV into the buy-group reporting SQLite database."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path


EXPECTED_HEADERS = [
    "Document", "Inv Type", "Account", "Name", "Job",
    "Sales/ Material Branch", "Date", "Accounting Year",
    "Accounting Period", "Item Ext Price", "Item Ext Cost", "Invoice GM",
    "Item", "Description", "Quantity", "Unit Price", "Unitcost", "Item GM",
]


def number(value: str):
    value = value.strip()
    return float(value) if value else None


def integer(value: str):
    value = value.strip()
    return int(value) if value else None


def import_sales(csv_path: Path, db_path: Path) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript((Path(__file__).parent / "schema.sql").read_text())
        with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != EXPECTED_HEADERS:
                raise ValueError(
                    "Unexpected sales headers. Expected "
                    f"{EXPECTED_HEADERS}; received {reader.fieldnames}"
                )
            rows = []
            for row in reader:
                rows.append((
                    row["Document"].strip(), row["Inv Type"].strip(),
                    row["Account"].strip(), row["Name"].strip(), row["Job"].strip(),
                    row["Sales/ Material Branch"].strip(), row["Date"].strip(),
                    integer(row["Accounting Year"]), integer(row["Accounting Period"]),
                    number(row["Item Ext Price"]), number(row["Item Ext Cost"]),
                    number(row["Invoice GM"]), row["Item"].strip(),
                    row["Description"].strip(), number(row["Quantity"]),
                    number(row["Unit Price"]), number(row["Unitcost"]),
                    number(row["Item GM"]), csv_path.name,
                ))
        connection.execute("DELETE FROM sales_transactions WHERE source_file = ?", (csv_path.name,))
        connection.executemany(
            """INSERT INTO sales_transactions (
                document, invoice_type, account_number, customer_name, job,
                sales_material_branch, sale_date, accounting_year, accounting_period,
                item_ext_price, item_ext_cost, invoice_gm, item_number, item_description,
                quantity, unit_price, unit_cost, item_gm, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        connection.commit()
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--database", type=Path, default=Path(__file__).parent / "data" / "buy_groups.sqlite3")
    args = parser.parse_args()
    count = import_sales(args.csv_path, args.database)
    print(f"Imported {count:,} sales rows into {args.database}")


if __name__ == "__main__":
    main()
