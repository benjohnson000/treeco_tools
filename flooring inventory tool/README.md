# Flooring inventory importer

Builds `data/inventory.db` from the daily ECI stock-status CSV and the Timeless dealer price list.

```powershell
python import_inventory.py `
  --prices "data\Timeless Dealer Price List January 2026 .xlsx" `
  --stock "data\Stock_Status_Flooring_TREECO(20260728112011).CSV"
```

The database contains:

- `products`: SKU, description, collection, price per square foot, and total stock.
- `stock_by_branch`: one row per SKU and branch.
- `imports`: source files and import timestamp.

Branch codes are currently mapped in `DEFAULT_BRANCHES` in the script. To override them without editing the script, pass a JSON file such as `{"5000":"Calgary","7000":"Edmonton","8000":"Vancouver"}` with `--branches`.

## Run the website

```powershell
py import_inventory.py
py server.py
```

Open `http://localhost:8080`. Other computers on the same network can use the mini-server's IP address with port `8080`.
