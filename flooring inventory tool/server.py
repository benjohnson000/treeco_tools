#!/usr/bin/env python3
import json, sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "inventory.db"

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/api/inventory":
            query = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
            con = sqlite3.connect(DB)
            branches = [r[0] for r in con.execute("SELECT DISTINCT branch FROM stock_by_branch ORDER BY branch")]
            params = []
            where = ""
            if query:
                where = "WHERE p.sku LIKE ? OR p.description LIKE ?"
                params = [f"%{query}%", f"%{query}%"]
            products = con.execute(f"SELECT p.sku, p.description, p.collection, p.total_stock FROM products p {where} ORDER BY p.collection, p.description, p.sku", params).fetchall()
            output = []
            for sku, description, collection, total in products:
                stock = dict(con.execute("SELECT branch, quantity FROM stock_by_branch WHERE sku=?", (sku,)))
                output.append({"sku": sku, "description": description, "collection": collection or "", "total_stock": total, "branches": {b: stock.get(b, 0) for b in branches}})
            con.close()
            body = json.dumps({"branches": branches, "products": output}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        super().do_GET()

if __name__ == "__main__":
    print("Inventory site: http://localhost:8080")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
