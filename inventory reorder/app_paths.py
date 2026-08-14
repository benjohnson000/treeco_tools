"""Application folders for the Railway web deployment."""

import os
import shutil
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = APP_DIR / "data"
DATA_DIR = Path(
    os.environ.get("DATA_DIR")
    or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    or DEFAULT_DATA_DIR
)
IMPORT_DIR = DATA_DIR / "imports"
DATABASE_FILE = DATA_DIR / "inventory.db"


def ensure_data_directories():
    """Create user-accessible folders on first run."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    # A Railway volume starts empty. Preserve any user-edited files and seed
    # only the default application assets that have not been created yet.
    if DATA_DIR != DEFAULT_DATA_DIR:
        for source_name, destination_name in (
            ("flooring_vendors.csv", "flooring_vendors.csv"),
            # The source file uses an uppercase extension; the application
            # consistently reads the lower-case name on Linux/Railway.
            ("vendors.CSV", "vendors.csv"),
            ("branches.json", "branches.json"),
            ("settings.json", "settings.json"),
            ("treeco-horizontal-logo-white.png", "treeco-horizontal-logo-white.png"),
        ):
            source, destination = DEFAULT_DATA_DIR / source_name, DATA_DIR / destination_name
            if source.exists() and not destination.exists():
                shutil.copy2(source, destination)
