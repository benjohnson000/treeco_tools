if (Get-Process -Name "SpruceInventoryReorder", "Spruce Reorder Tool" -ErrorAction SilentlyContinue) {
    throw "Close Spruce Inventory Reorder before building a new version."
}

if (Test-Path dist\data) { Remove-Item -LiteralPath dist\data -Recurse -Force }
if (Test-Path dist\inventory.db) { Remove-Item -LiteralPath dist\inventory.db -Force }
if (Test-Path 'dist\SpruceInventoryReorder.exe') { Remove-Item -LiteralPath 'dist\SpruceInventoryReorder.exe' -Force }

if (-not (Test-Path icon.ico)) {
    if (-not (Test-Path logo.png)) {
        throw "icon.ico was not found and there is no logo.png available to create one."
    }
    & python prepare_icon.py
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create icon.ico from logo.png."
    }
}

& python -m PyInstaller --clean --noconfirm --onefile --windowed --icon=icon.ico --name "Spruce Reorder Tool" desktop_app.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller could not build the desktop application."
}
New-Item -ItemType Directory -Path dist\data -Force | Out-Null
Copy-Item data\branches.json dist\data\branches.json -Force
Copy-Item data\flooring_vendors.csv dist\data\flooring_vendors.csv -Force
Copy-Item data\vendors.csv dist\data\vendors.csv -Force
Copy-Item data\settings.json dist\data\settings.json -Force
