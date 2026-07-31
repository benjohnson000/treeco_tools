# Buy Group Reporting

This project stores historical sales in SQLite and associates accounts with buy groups. It also includes a blank native Windows dashboard shell, ready for reporting features.

## Run the dashboard

Install the desktop dependencies once:

```powershell
python -m pip install -r requirements.txt
```

Then double-click `start_app.bat`, or run:

```powershell
python desktop_app.py
```

## Build a standalone `.exe`

From PowerShell, run:

```powershell
.\build_desktop.ps1
```

The application is created at `dist\Treeco Buy Group Reporting.exe`.

## Local application data

The dashboard saves uploaded essentials, including the Account Number vs Buy Group CSV and the SQLite sales database, in:

`%LOCALAPPDATA%\Treeco\Buy Group Reporting\data`

Sales uploads are stored in `buy_group_reporting.sqlite`.

## Import the supplied CSV files

From this directory:

```powershell
python import_data.py `
  "C:\Users\ConorKarperien\Downloads\Salesdatajune2026.csv" `
  "C:\Users\ConorKarperien\Downloads\Account Number vs Buy Group.CSV"
```

The default output is `buy_group_reporting.sqlite`. Re-running the command adds another sales import batch; it replaces duplicate account mappings.

## Useful query

```sql
SELECT
  COALESCE(bg.buy_group, 'Unassigned') AS buy_group,
  SUM(s.item_ext_price) AS sales,
  SUM(s.item_ext_cost) AS cost,
  SUM(s.item_ext_price - s.item_ext_cost) AS gross_margin
FROM sales s
LEFT JOIN buy_groups bg ON bg.account_number = s.account_number
GROUP BY COALESCE(bg.buy_group, 'Unassigned')
ORDER BY sales DESC;
```

Dates are stored as ISO text (`YYYY-MM-DD`), while monetary and quantity fields are stored as SQLite `REAL` values.
