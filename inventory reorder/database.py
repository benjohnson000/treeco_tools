import pandas as pd
from sqlalchemy import create_engine, inspect

from app_paths import DATABASE_FILE, ensure_data_directories

ensure_data_directories()
engine = create_engine(f"sqlite:///{DATABASE_FILE.as_posix()}")


def replace_imported_data(inventory, usage):
    """Replace the current in-session multi-branch report snapshot."""
    engine.dispose()
    inventory.to_sql("inventory", engine, if_exists="replace", index=False)
    usage.to_sql("usage_history", engine, if_exists="replace", index=False)


def clear_imported_data():
    """Remove the current in-session inventory snapshot."""
    engine.dispose()
    if DATABASE_FILE.exists():
        DATABASE_FILE.unlink()


def refresh_inventory_vendors(vendor_map):
    """Apply an updated SKU-to-vendor mapping to the current inventory."""
    engine.dispose()
    if "inventory" not in inspect(engine).get_table_names():
        return 0

    inventory = pd.read_sql("SELECT * FROM inventory", engine)
    inventory["vendor"] = inventory["sku"].map(
        lambda sku: vendor_map.get(str(sku).strip().casefold())
    )
    inventory.to_sql("inventory", engine, if_exists="replace", index=False)
    return int(inventory["vendor"].notna().sum())
