"""Application folders that work in development and packaged desktop builds."""

from pathlib import Path
import sys


# PyInstaller unpacks code to a temporary folder. User data must stay beside
# the executable so it remains available between runs and upgrades.
APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
DATA_DIR = APP_DIR / "data"
IMPORT_DIR = DATA_DIR / "imports"
DATABASE_FILE = APP_DIR / "inventory.db"


def ensure_data_directories():
    """Create user-accessible folders on first run."""
    DATA_DIR.mkdir(exist_ok=True)
    IMPORT_DIR.mkdir(exist_ok=True)
