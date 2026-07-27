if (Test-Path dist\data) { Remove-Item -LiteralPath dist\data -Recurse -Force }
if (Test-Path dist\inventory.db) { Remove-Item -LiteralPath dist\inventory.db -Force }

& python -m PyInstaller --onefile --windowed --name SpruceInventoryReorder desktop_app.py
New-Item -ItemType Directory -Path dist\data -Force | Out-Null
Copy-Item data\branches.json dist\data\branches.json -Force
Copy-Item data\flooring_vendors.csv dist\data\flooring_vendors.csv -Force
Copy-Item settings.json dist\settings.json -Force
