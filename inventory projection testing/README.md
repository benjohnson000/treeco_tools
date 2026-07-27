# Spruce Inventory Reorder Tool

## Daily workflow

1. Double-click `start_app.bat`.
2. Generate the Spruce Stock Status CSV and the 12-month Usage CSV.
3. Upload both files in the Import Spruce reports section.
4. Review the recommendations, adjust order amounts, and download the consolidated order CSV.

## User-accessible data

- `data/flooring_vendors.csv`: SKU-to-vendor-code mapping.
- `data/vendors.csv`: Vendor-code-to-name mapping for the vendor filter.
- `data/branches.json`: configured branch names and IDs.
- `data/imports/`: archived source reports from every successful import.
- `inventory.db`: temporary database for the current application session.

## First-time setup

Install Python 3.11 or newer, selecting **Add Python to PATH**, then run:

```powershell
python -m pip install -r requirements.txt
```

After that, double-click `start_app.bat` to open the native desktop tool.

## Build a standalone Windows executable

Run `./build_desktop.ps1` from PowerShell. The distributable application is
created in `dist`. Keep `SpruceInventoryReorder.exe`, `settings.json`, and the
`data` folder together when copying the tool to another computer.
