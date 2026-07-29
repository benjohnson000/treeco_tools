#!/usr/bin/env python3
import html, hmac, json, os, sqlite3, subprocess, tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "inventory.db"

class Handler(SimpleHTTPRequestHandler):
    def multipart_fields(self, body, content_type):
        boundary = content_type.split("boundary=", 1)[-1].strip().strip('"').encode()
        fields = {}
        for part in body.split(b"--" + boundary):
            if b"\r\n\r\n" not in part: continue
            raw_headers, value = part.split(b"\r\n\r\n", 1)
            disposition = next((x for x in raw_headers.decode("utf-8", "ignore").split("\r\n") if x.lower().startswith("content-disposition:")), "")
            name = next((x.split("=", 1)[1].strip(' \"') for x in disposition.split(";") if x.strip().startswith("name=")), "")
            filename = next((x.split("=", 1)[1].strip(" \"'") for x in disposition.split(";") if x.strip().startswith("filename=")), "")
            fields[name] = {"value": value.rstrip(b"\r\n-"), "filename": filename}
        return fields

    def send_html(self, status, content):
        body = content.encode()
        self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/admin/upload":
            self.send_error(404); return
        expected = os.environ.get("ADMIN_PASSWORD", "")
        length = int(self.headers.get("Content-Length", "0"))
        if length > 20 * 1024 * 1024:
            self.send_html(413, "<h1>Upload too large</h1>"); return
        fields = self.multipart_fields(self.rfile.read(length), self.headers.get("Content-Type", ""))
        password = fields.get("password", {}).get("value", b"").decode("utf-8", "ignore")
        file_item = fields.get("stock_file")
        if not expected or not hmac.compare_digest(password, expected):
            self.send_html(401, "<h1>Upload not authorized</h1><p>Check the admin password.</p>"); return
        if not file_item or not file_item.get("filename"):
            self.send_html(400, "<h1>No CSV selected</h1>"); return
        if not file_item["filename"].lower().endswith(".csv"):
            self.send_html(400, "<h1>Only CSV files are accepted</h1>"); return
        with tempfile.TemporaryDirectory(dir=ROOT / "data") as tmp:
            stock_file = Path(tmp) / Path(file_item["filename"]).name
            stock_file.write_bytes(file_item["value"])
            new_db = Path(tmp) / "inventory.db"
            command = [os.environ.get("PYTHON", "python"), str(ROOT / "import_inventory.py"), "--prices", str(ROOT / "data" / "Timeless Dealer Price List January 2026 .xlsx"), "--stock", str(stock_file), "--output", str(new_db)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
            if result.returncode != 0 or not new_db.exists():
                self.send_html(422, "<h1>Import failed</h1><pre>" + html.escape(result.stderr or result.stdout) + "</pre>"); return
            os.replace(new_db, DB)
        self.send_html(200, "<h1>Inventory updated</h1><p>The CSV was processed successfully.</p><p><a href='/'>View inventory</a></p>")

    def do_GET(self):
        if urlparse(self.path).path == "/admin/upload":
            self.send_html(200, """<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>Inventory admin</title><style>body{font:16px Arial;max-width:560px;margin:60px auto;padding:20px}label{display:block;margin:18px 0 6px}input,button{font:inherit;padding:10px;width:100%}button{margin-top:22px;cursor:pointer}</style><h1>Update inventory</h1><p>For authorized staff only.</p><form method='post' enctype='multipart/form-data'><label for='password'>Admin password</label><input id='password' name='password' type='password' required><label for='stock_file'>Stock status CSV</label><input id='stock_file' name='stock_file' type='file' accept='.csv,text/csv' required><button>Upload and process</button></form>"""); return
        self.public_get()

    def public_get(self):
        if urlparse(self.path).path == "/api/inventory":
            query = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
            con = sqlite3.connect(DB)
            branches = [r[0] for r in con.execute("SELECT DISTINCT branch FROM stock_by_branch ORDER BY branch")]
            params = []
            where = ""
            if query:
                where = "WHERE p.sku LIKE ? OR p.description LIKE ?"
                params = [f"%{query}%", f"%{query}%"]
            products = con.execute(f"SELECT p.sku, p.description, p.collection, p.carton_sqft, p.total_stock, p.consolidated, p.source_skus FROM products p {where} ORDER BY p.collection, p.description, p.sku", params).fetchall()
            output = []
            for sku, description, collection, carton_sqft, total, consolidated, source_skus in products:
                stock = dict(con.execute("SELECT branch, quantity FROM stock_by_branch WHERE sku=?", (sku,)))
                output.append({"sku": sku, "description": description, "collection": collection or "", "carton_sqft": carton_sqft, "total_stock": total, "consolidated": bool(consolidated), "source_skus": source_skus or "", "branches": {b: stock.get(b, 0) for b in branches}})
            con.close()
            body = json.dumps({"branches": branches, "products": output}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        super().do_GET()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Inventory site listening on port {port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
