# Buy Group Reporting

Initial database setup for the buy-group report generator.

## Import June sales

```powershell
python import_sales.py "C:\Users\ConorKarperien\Downloads\Salesdatajune2026.csv"
```

The SQLite database is created at `data/buy_groups.sqlite3`. Re-running the command replaces rows imported from the same source filename, so the import is safe to repeat.

The current schema stores the June sales file as one row per sales item and keeps the original source filename for traceability. Buy-group mappings and report generation will be added next.
