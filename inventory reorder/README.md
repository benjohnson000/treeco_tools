# Spruce Inventory Reorder Tool

## Daily workflow

1. Open the deployed Railway application.
2. Generate the Spruce Stock Status CSV and the 12-month Usage CSV.
3. Upload both files in the Import Spruce reports section.
4. Review the recommendations, adjust order amounts, and download the consolidated order CSV.

## User-accessible data

- `data/flooring_vendors.csv`: SKU-to-vendor-code mapping.
- `data/vendors.csv`: Vendor-code-to-name mapping for the vendor filter.
- `data/branches.json`: configured branch names and IDs.
- `data/settings.json`: reorder settings.
- `data/treeco-horizontal-logo-white.png`: Treeco dashboard logo.
- `data/imports/`: archived source reports from every successful import.
- `inventory.db`: temporary database for the current application session.

To update SKU vendor assignments, use the **Vendor mapping** panel in the web
application to upload Spruce's CSV containing `SKU` and `Vendor` columns.

## Deploy internally on Railway

Create a Railway service using this folder as its root directory. The included
`Dockerfile` and `railway.json` run the browser version of the tool.

Set these Railway variables:

- `APP_PASSWORD`: required password for the internal site.
- `APP_USERNAME`: optional username; defaults to `treeco`.

Create a Railway volume and mount it at `/data`. The tool stores its settings,
vendor and branch configuration, imported reports, and the active inventory
database there. On its first run, it copies the default configuration files to
the empty volume; later changes persist across deployments.

The application downloads the consolidated order CSV directly in the browser.
