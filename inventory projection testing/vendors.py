from pathlib import Path
import csv

from app_paths import DATA_DIR

VENDORS_FILE = DATA_DIR / "vendors.txt"
VENDOR_MAP_FILE = DATA_DIR / "flooring_vendors.csv"


def load_vendors(filename=VENDORS_FILE):
    """Load vendor names from a plain text file, one vendor per line."""
    path = Path(filename)
    if not path.exists():
        return []

    vendors = []
    with open(path, encoding="utf-8") as file:
        for line in file:
            vendor = line.strip()
            if vendor and not vendor.startswith("#"):
                vendors.append(vendor)

    return sorted(vendors, key=len, reverse=True)


def find_vendor(description, vendors):
    """Return the first vendor name found in an item description."""
    if not isinstance(description, str):
        return None

    normalized_description = description.casefold()
    for vendor in vendors:
        if vendor.casefold() in normalized_description:
            return vendor

    return None


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
