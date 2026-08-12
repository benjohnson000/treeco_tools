from pathlib import Path
import csv

from app_paths import DATA_DIR

VENDOR_MAP_FILE = DATA_DIR / "flooring_vendors.csv"
VENDOR_NAMES_FILE = DATA_DIR / "vendors.csv"


def load_vendor_map(filename=VENDOR_MAP_FILE):
    """Load the authoritative SKU-to-vendor-code mapping export."""
    mapping = {}
    path = Path(filename)
    if not path.exists():
        return mapping
    with open(path, encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            sku = (row.get("SKU") or "").strip()
            vendor = (row.get("Vendor") or "").strip()
            if sku:
                mapping[sku] = vendor or None
    return mapping


def find_vendor_by_sku(sku, vendor_map):
    return vendor_map.get(str(sku).strip())


def load_vendor_names(filename=VENDOR_NAMES_FILE):
    """Load the vendor-code-to-name export used by the dashboard filter."""
    vendor_names = {}
    path = Path(filename)
    if not path.exists():
        return vendor_names

    with open(path, encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file):
            if len(row) < 2:
                continue
            vendor_code = row[0].strip()
            vendor_name = row[1].strip()
            if vendor_code and vendor_name and vendor_code.casefold() != "vendor":
                vendor_names[vendor_code] = vendor_name
    return vendor_names
