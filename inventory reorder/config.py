import json

from app_paths import APP_DIR, DATA_DIR, ensure_data_directories

SETTINGS_FILE = DATA_DIR / "settings.json"
LEGACY_SETTINGS_FILE = APP_DIR / "settings.json"
REQUIRED_SETTINGS = (
    "stock_target_days",
    "vendor_lead_time_days",
    "buffer_days",
)


def load_settings(filename=SETTINGS_FILE):
    """Load and validate the reorder settings kept beside the application."""
    filename = _migrate_legacy_settings(filename)
    with open(filename, encoding="utf-8") as file:
        settings = json.load(file)

    return _validate_settings(settings)


def save_settings(settings, filename=SETTINGS_FILE):
    """Validate and persist settings selected in the dashboard."""
    validated_settings = _validate_settings(settings)
    ensure_data_directories()

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(validated_settings, file, indent=2)
        file.write("\n")


def _migrate_legacy_settings(filename):
    """Copy existing root-level settings into the data folder on first run."""
    if filename == SETTINGS_FILE and not SETTINGS_FILE.exists() and LEGACY_SETTINGS_FILE.exists():
        with open(LEGACY_SETTINGS_FILE, encoding="utf-8") as file:
            legacy_settings = json.load(file)
        save_settings(legacy_settings, SETTINGS_FILE)
    return filename


def _validate_settings(settings):
    validated_settings = {}

    for name in REQUIRED_SETTINGS:
        if name not in settings:
            raise ValueError(f"Missing required setting: {name}")
        if not isinstance(settings[name], (int, float)) or settings[name] < 0:
            raise ValueError(f"{name} must be a non-negative number")
        validated_settings[name] = settings[name]

    return validated_settings
