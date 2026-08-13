import json

from app_paths import APP_DIR, DATA_DIR, ensure_data_directories

SETTINGS_FILE = DATA_DIR / "settings.json"
LEGACY_SETTINGS_FILE = APP_DIR / "settings.json"
REQUIRED_SETTINGS = (
    "stock_target_days",
    "vendor_lead_time_days",
)
LOCATION_REMAP_DEFAULTS = {
    "location_remap_enabled": False,
    "location_remap_sources": ["1000", "2000", "4000", "6000"],
    "location_remap_target": "8000",
}


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

    enabled = settings.get(
        "location_remap_enabled", LOCATION_REMAP_DEFAULTS["location_remap_enabled"]
    )
    if not isinstance(enabled, bool):
        raise ValueError("location_remap_enabled must be true or false")

    sources = settings.get(
        "location_remap_sources", LOCATION_REMAP_DEFAULTS["location_remap_sources"]
    )
    if not isinstance(sources, list) or not all(str(source).strip() for source in sources):
        raise ValueError("location_remap_sources must be a list of location IDs")

    target = str(settings.get(
        "location_remap_target", LOCATION_REMAP_DEFAULTS["location_remap_target"]
    )).strip()
    if not target:
        raise ValueError("location_remap_target must be a location ID")
    if target in {str(source).strip() for source in sources}:
        raise ValueError("The remap target cannot also be a source location")

    validated_settings.update({
        "location_remap_enabled": enabled,
        "location_remap_sources": [str(source).strip() for source in sources],
        "location_remap_target": target,
    })

    return validated_settings
