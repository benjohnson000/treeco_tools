from sqlalchemy import create_engine

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
