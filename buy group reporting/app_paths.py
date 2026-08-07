"""Paths for data that must persist outside the packaged application."""

import os
from pathlib import Path


TREECO_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Treeco"
APP_DATA_DIR = TREECO_DATA_DIR / "Buy Group Reporting"
DATA_DIR = Path(
    os.environ.get("DATA_DIR")
    or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    or APP_DATA_DIR / "data"
)
BUY_GROUPS_FILE = DATA_DIR / "account_number_vs_buy_group.csv"
SALES_DATABASE = DATA_DIR / "buy_group_reporting.sqlite"


def ensure_data_directory():
    """Create and return the folder used for locally saved application data."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
