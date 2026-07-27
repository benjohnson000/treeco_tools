from pathlib import Path
import csv

from app_paths import DATA_DIR

VENDOR_MAP_FILE = DATA_DIR / "flooring_vendors.csv"


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
