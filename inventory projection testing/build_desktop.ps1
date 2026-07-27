& python -m PyInstaller --onefile --windowed --name SpruceInventoryReorder desktop_app.py
Copy-Item data dist\data -Recurse -Force
Copy-Item settings.json dist\settings.json -Force
