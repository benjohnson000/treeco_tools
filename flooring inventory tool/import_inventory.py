#!/usr/bin/env python3
"""Build the flooring inventory database from ECI stock and Timeless pricing files."""
from __future__ import annotations

import argparse, csv, datetime as dt, json, re, sqlite3, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

DEFAULT_BRANCHES = {"5000": "Calgary", "7000": "Edmonton", "8000": "Vancouver"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def clean(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\\", "")).strip()

def xlsx_rows(path: Path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append(clean("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        for sheet in wb.find("m:sheets", NS):
            target = relmap[sheet.attrib["{%s}id" % NS["r"]]]
            target = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            root = ET.fromstring(z.read(target))
            rows = []
            for row in root.findall(".//m:sheetData/m:row", NS):
                vals = {}
                for c in row.findall("m:c", NS):
                    ref = c.attrib.get("r", "A1")
                    col = 0
                    for ch in re.match(r"[A-Z]+", ref).group(): col = col * 26 + ord(ch) - 64
                    val = c.find("m:v", NS)
                    text = "" if val is None else val.text or ""
                    if c.attrib.get("t") == "s" and text: text = shared[int(text)]
                    vals[col - 1] = text
                rows.append([vals.get(i, "") for i in range(max(vals.keys(), default=-1) + 1)])
            yield sheet.attrib["name"], rows

def parse_prices(path: Path):
    products = {}
    for sheet, rows in xlsx_rows(path):
        if not sheet.startswith("TL Page"): continue
        collection = None
        for row in rows:
            cells = [clean(x) for x in row]
            joined = " ".join(x for x in cells if x)
            if not joined: continue
            heading = re.sub(r"(?<![A-Za-z])(?:[A-Z]\s+){2,}[A-Z]", lambda m: m.group(0).replace(" ", ""), joined)
            m = re.search(r"(.{2,80}?)(?:\s*)COLLECTION", heading, re.I)
            if m and len(joined) < 180 and not any(x in joined.lower() for x in ("construction", "radiant heat")):
                collection = re.sub(r"\s+", " ", m.group(1).title()).strip(" -*")
            sku = ""
            for idx in (1, 5):
                if idx < len(cells) and re.fullmatch(r"[A-Za-z0-9]+", cells[idx]) and any(ch.isdigit() for ch in cells[idx]):
                    sku = cells[idx].upper(); break
            if not sku or sku.lower() in {"sku", "sku #"}: continue
            description = cells[0] if cells else ""
            carton_sqft = None
            if len(cells) > 2:
                carton_match = re.search(r"([\d.]+)\s*(?:sq\.?\s*ft|sqft)", cells[2], re.I)
                if carton_match: carton_sqft = float(carton_match.group(1))
            price = None
            for idx in (7, 5):
                if idx < len(cells) and re.fullmatch(r"\d+(?:\.\d+)?", cells[idx]):
                    price = float(cells[idx]); break
            products[sku] = {"sku": sku, "description": description, "collection": collection, "price_per_sqft": price, "carton_sqft": carton_sqft}
    return products

def parse_stock(path: Path, branch_names):
    result, current_sku, current_desc = {}, None, None
    report_date = None
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            cells = [clean(x) for x in row]
            if cells and cells[0].startswith("Branch:"):
                if len(cells) > 3: report_date = cells[3]
                continue
            if current_sku and len(cells) >= 5 and cells[0] in branch_names:
                numeric = lambda x: re.fullmatch(r"-?[\d,]+(?:\.\d+)?", x or "")
                if all(numeric(x) for x in cells[1:5]):
                    result[current_sku]["branches"][branch_names[cells[0]]] = float(cells[1].replace(",", ""))
                    continue
            if len(cells) >= 2 and re.fullmatch(r"[A-Za-z0-9]+", cells[0]) and not all(not x for x in cells[1:]):
                # SKU rows have a description and do not have numeric inventory fields.
                if cells[0].upper() not in {"ITEM", "DESCRIPTION"} and not all(re.fullmatch(r"-?[\d,]+(?:\.\d+)?", x or "") for x in cells[1:6]):
                    current_sku, current_desc = cells[0].upper(), cells[1]
                    result.setdefault(current_sku, {"description": current_desc, "branches": {}})
                    continue
            if current_sku and len(cells) >= 5 and cells[0] in branch_names and all(re.fullmatch(r"-?\d+(?:\.\d+)?", x or "") for x in cells[1:5]):
                result[current_sku]["branches"][branch_names[cells[0]]] = float(cells[1])
    return result, report_date

def merge_variant_skus(prices, stock):
    """Combine distributor-style trailing-V variants, but never combine HB products."""
    merged = {}
    for sku in list(set(prices) | set(stock)):
        # HBR is a herringbone distributor variant of the corresponding HB SKU.
        # Other trailing-V variants are consolidated only for non-HB products.
        if sku.endswith("HBR"):
            base = sku[:-1]
        elif sku.endswith("V") and not sku.endswith("HBV"):
            base = sku[:-1]
        else:
            continue
        if base not in prices and base not in stock:
            continue
        canonical = base if sku.endswith("HBR") or base in prices else sku
        other = sku if canonical == base else base
        merged.setdefault(canonical, [canonical]).append(other)
        if other in prices and canonical not in prices:
            prices[canonical] = prices[other]
        if other in stock:
            target = stock.setdefault(canonical, {"description": "", "branches": {}})
            for branch, qty in stock[other].get("branches", {}).items():
                target["branches"][branch] = target["branches"].get(branch, 0) + qty
            if not target.get("description"): target["description"] = stock[other].get("description", "")
        if other != canonical:
            prices.pop(other, None)
            stock.pop(other, None)
    return prices, stock, merged

def build_db(price_path, stock_path, output, branch_names):
    prices = parse_prices(price_path)
    stock, report_date = parse_stock(stock_path, branch_names)
    prices, stock, merged = merge_variant_skus(prices, stock)
    # Keep discontinued ## items only while they still have stock somewhere.
    # Template placeholders beginning with < are always excluded.
    for sku in set(prices) | set(stock):
        price_item, stock_item = prices.get(sku, {}), stock.get(sku, {})
        description = price_item.get("description") or stock_item.get("description") or ""
        total_stock = sum(stock_item.get("branches", {}).values())
        if description.lstrip().startswith("<") or (description.lstrip().startswith("##") and total_stock <= 0):
            prices.pop(sku, None)
            stock.pop(sku, None)
    output.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(output)
    con.executescript("""
    DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS stock_by_branch; DROP TABLE IF EXISTS imports;
    CREATE TABLE products (sku TEXT PRIMARY KEY, description TEXT NOT NULL, collection TEXT, price_per_sqft REAL, carton_sqft REAL, total_stock REAL NOT NULL DEFAULT 0, consolidated INTEGER NOT NULL DEFAULT 0, source_skus TEXT);
    CREATE TABLE stock_by_branch (sku TEXT NOT NULL, branch TEXT NOT NULL, quantity REAL NOT NULL DEFAULT 0, PRIMARY KEY (sku, branch), FOREIGN KEY (sku) REFERENCES products(sku));
    CREATE TABLE imports (id INTEGER PRIMARY KEY, imported_at TEXT NOT NULL, stock_report_date TEXT, price_file TEXT, stock_file TEXT);
    """)
    skus = sorted(set(prices) | set(stock))
    for sku in skus:
        p, s = prices.get(sku, {}), stock.get(sku, {})
        branches = s.get("branches", {})
        total = sum(branches.values())
        source_skus = merged.get(sku, [])
        con.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)", (sku, p.get("description") or s.get("description") or sku, p.get("collection"), p.get("price_per_sqft"), p.get("carton_sqft"), total, int(bool(source_skus)), ", ".join(source_skus) if source_skus else None))
        for branch, qty in branches.items(): con.execute("INSERT INTO stock_by_branch VALUES (?,?,?)", (sku, branch, qty))
    con.execute("INSERT INTO imports(imported_at,stock_report_date,price_file,stock_file) VALUES (?,?,?,?)", (dt.datetime.now().isoformat(timespec="seconds"), report_date, str(price_path), str(stock_path)))
    con.commit(); con.close()
    return len(skus), len(prices), len(stock)

def print_table(output: Path):
    con = sqlite3.connect(output)
    branches = [r[0] for r in con.execute("SELECT DISTINCT branch FROM stock_by_branch ORDER BY branch")]
    headers = ["SKU", "Description", "Collection", "Total Stock"] + branches
    rows = []
    for row in con.execute("SELECT sku, description, collection, total_stock FROM products ORDER BY collection, description, sku"):
        sku, description, collection, total = row
        quantities = dict(con.execute("SELECT branch, quantity FROM stock_by_branch WHERE sku=?", (sku,)))
        rows.append([sku, description, collection or "", f"{total:g}"] + [f"{quantities.get(b, 0):g}" for b in branches])
    con.close()
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    print("\n" + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))

def main():
    ap = argparse.ArgumentParser()
    data_dir = Path(__file__).resolve().parent / "data"
    default_prices = data_dir / "Timeless Dealer Price List January 2026 .xlsx"
    stock_files = sorted(data_dir.glob("Stock_Status_Flooring_*.CSV"), key=lambda p: p.stat().st_mtime, reverse=True)
    default_stock = stock_files[0] if stock_files else data_dir / "Stock_Status_Flooring_TREECO.CSV"
    ap.add_argument("--prices", type=Path, default=default_prices)
    ap.add_argument("--stock", type=Path, default=default_stock)
    ap.add_argument("--output", type=Path, default=data_dir / "inventory.db")
    ap.add_argument("--branches", type=Path, help="JSON mapping of ECI branch codes to names")
    args = ap.parse_args()
    branches = DEFAULT_BRANCHES if not args.branches else {str(k): v for k, v in json.loads(args.branches.read_text()).items()}
    print("Imported", build_db(args.prices, args.stock, args.output, branches), "->", args.output)
    print_table(args.output)

if __name__ == "__main__": main()
