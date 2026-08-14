import csv
import io

import pandas as pd

from branches import load_branches
from vendors import find_vendor_by_sku, load_vendor_map


STOCK_COLUMNS = [
    "sku", "description", "branch_id", "branch_name", "on_hand", "on_order",
    "available", "min_qty", "max_qty", "suggested_qty", "unit", "last_received",
    "last_cost", "avg_cost", "vendor",
]
USAGE_COLUMNS = [
    "sku", "branch_id", "last_12_month_sales", "last_6_month_sales",
    "previous_6_month_sales",
]


def load_spruce_stock(filename, vendors_filename=None, branches_filename=None):
    """Load a combined Spruce Stock Status report into one SKU/branch row."""
    branches = load_branches(branches_filename) if branches_filename else load_branches()
    vendor_map = load_vendor_map(vendors_filename) if vendors_filename else load_vendor_map()
    records = []
    current_item = None

    for row in _csv_rows(filename):
        if _is_stock_report_row(row):
            continue

        if _is_item_row(row):
            current_item = {"sku": row[0].strip(), "description": row[1].strip()}
            continue

        if not current_item or not _is_branch_stock_row(row, branches):
            continue

        records.append({
            "sku": current_item["sku"],
            "description": current_item["description"],
            "branch_id": row[0].strip(),
            "branch_name": branches[row[0].strip()],
            "on_hand": _number(row[1]),
            "on_order": _number(row[2]),
            "available": _number(row[3]),
            "min_qty": _number(row[4]),
            "max_qty": _number(row[5]),
            "suggested_qty": _number(row[6]),
            "unit": row[7].strip(),
            "last_received": row[8].strip(),
            "last_cost": _number(row[9]),
            "avg_cost": _number(row[10]),
            "vendor": find_vendor_by_sku(current_item["sku"], vendor_map),
        })

    inventory = pd.DataFrame(records, columns=STOCK_COLUMNS)
    if inventory.empty:
        return inventory

    return inventory.loc[
        ~inventory["description"].str.strip().str.startswith("##")
    ].reset_index(drop=True)


def load_spruce_usage(filename, branches_filename=None):
    """Load Spruce's 12-month monthly sales report into one row per SKU/branch."""
    branches = load_branches(branches_filename) if branches_filename else load_branches()
    records = []
    current_sku = None
    month_columns = None

    for row in _csv_rows(filename):
        if _is_usage_header(row):
            month_columns = _usage_month_columns(row)
            continue
        if _is_usage_report_row(row):
            continue

        if _is_item_row(row):
            current_sku = row[0].strip()
            continue

        if not current_sku or month_columns is None or not _is_branch_usage_row(row, branches):
            continue

        monthly_sales = [_number(row[index]) for index in range(2, 14)]
        records.append({
            "sku": current_sku,
            "branch_id": row[0].strip(),
            "last_12_month_sales": sum(monthly_sales),
            "previous_6_month_sales": sum(monthly_sales[:6]),
            "last_6_month_sales": sum(monthly_sales[6:]),
        })

    if month_columns is None:
        raise ValueError(
            "This is not the 12-month Spruce usage report. "
            "Upload the report with 12 monthly columns and a Total column."
        )
    return pd.DataFrame(records, columns=USAGE_COLUMNS)


def load_spruce_single_branch_stock(
    filename, branch_id, vendors_filename=None, branches_filename=None
):
    """Load a single-branch Spruce Stock Status report."""
    branches = load_branches(branches_filename) if branches_filename else load_branches()
    branch_id = str(branch_id)
    if branch_id not in branches:
        raise ValueError(f"Unknown branch ID: {branch_id}")
    vendor_map = load_vendor_map(vendors_filename) if vendors_filename else load_vendor_map()
    records = []

    for row in _csv_rows(filename):
        if not _is_single_branch_stock_row(row):
            continue
        sku = row[0].strip()
        description = row[1].strip()
        records.append({
            "sku": sku,
            "description": description,
            "branch_id": branch_id,
            "branch_name": branches[branch_id],
            "on_hand": _number(row[2]),
            "on_order": _number(row[3]),
            "available": _number(row[4]),
            "min_qty": _number(row[5]) if len(row) > 5 else pd.NA,
            "max_qty": _number(row[6]) if len(row) > 6 else pd.NA,
            "suggested_qty": _number(row[7]) if len(row) > 7 else pd.NA,
            "unit": row[8].strip() if len(row) > 8 else "",
            "last_received": row[9].strip() if len(row) > 9 else "",
            "last_cost": _number(row[10]) if len(row) > 10 else pd.NA,
            "avg_cost": _number(row[11]) if len(row) > 11 else pd.NA,
            "vendor": find_vendor_by_sku(sku, vendor_map),
        })

    inventory = pd.DataFrame(records, columns=STOCK_COLUMNS)
    return inventory.loc[
        ~inventory["description"].str.strip().str.startswith("##")
    ].reset_index(drop=True)


def load_spruce_single_branch_usage(filename, branch_id, branches_filename=None):
    """Load a single-branch Spruce 12-month Usage report."""
    branches = load_branches(branches_filename) if branches_filename else load_branches()
    branch_id = str(branch_id)
    if branch_id not in branches:
        raise ValueError(f"Unknown branch ID: {branch_id}")
    records = []
    found_header = False

    for row in _csv_rows(filename):
        if _is_usage_header(row):
            _usage_month_columns(row)
            found_header = True
            continue
        if not found_header or not _is_single_branch_usage_row(row):
            continue
        monthly_sales = [_number(row[index]) for index in range(3, 15)]
        records.append({
            "sku": row[0].strip(),
            "branch_id": branch_id,
            "last_12_month_sales": sum(monthly_sales),
            "previous_6_month_sales": sum(monthly_sales[:6]),
            "last_6_month_sales": sum(monthly_sales[6:]),
        })

    if not found_header:
        raise ValueError(
            "This is not the 12-month Spruce usage report. "
            "Upload the report with 12 monthly columns and a Total column."
        )
    return pd.DataFrame(records, columns=USAGE_COLUMNS)


def _csv_rows(filename):
    if hasattr(filename, "read"):
        filename.seek(0)
        contents = filename.read()
        if isinstance(contents, bytes):
            contents = contents.decode("utf-8-sig")
        else:
            contents = contents.lstrip("\ufeff")
        rows = csv.reader(io.StringIO(contents), escapechar="\\")
        for row in rows:
            yield [value.strip() for value in row]
        return

    with open(filename, encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file, escapechar="\\"):
            yield [value.strip() for value in row]


def _is_item_row(row):
    # Item numbers may be numeric, but branch rows have a numeric quantity in
    # their second field while item rows have a text description.
    return len(row) >= 2 and row[0] and row[1] and not _looks_numeric(row[1])


def _is_branch_stock_row(row, branches):
    return len(row) >= 11 and row[0] in branches


def _is_branch_usage_row(row, branches):
    return len(row) >= 15 and row[0] in branches


def _is_single_branch_stock_row(row):
    return len(row) >= 5 and row[0] and row[1] and _looks_numeric(row[2])


def _is_single_branch_usage_row(row):
    return len(row) >= 16 and row[0] and row[1] and _looks_numeric(row[2])


def _is_usage_header(row):
    return bool(row) and row[0].casefold() == "item" and len(row) >= 15


def _usage_month_columns(row):
    months = row[2:-1]
    if len(months) != 12 or not all("/" in month for month in months):
        raise ValueError(
            "This is not the 12-month Spruce usage report. "
            "Upload the report with 12 monthly columns and a Total column."
        )
    return [f"sales_{month.replace('/', '_')}" for month in months]


def _is_stock_report_row(row):
    if not row:
        return True
    return row[0].startswith((
        "Branch:", "Inventory Stock Status", "All Keywords:", "Any Keywords:",
        "Item", "Page,",
    ))


def _is_usage_report_row(row):
    if not row:
        return True
    return row[0].startswith((
        "Branch:", "Inventory Usage", "KeyWord:", "Description", "Item", "Page,",
    ))


def _number(value):
    return pd.to_numeric(str(value).replace(",", ""), errors="coerce")


def _looks_numeric(value):
    return not pd.isna(_number(value))
