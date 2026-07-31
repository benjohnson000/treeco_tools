if (Get-Process -Name "Treeco Buy Group Reporting" -ErrorAction SilentlyContinue) {
    throw "Close Treeco Buy Group Reporting before building a new version."
}

& python -m PyInstaller --clean --noconfirm --onefile --windowed --name "Treeco Buy Group Reporting" desktop_app.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller could not build the desktop application."
}

Write-Output "Built: dist\\Treeco Buy Group Reporting.exe"
