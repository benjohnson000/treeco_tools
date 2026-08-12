"""Local Buy Group Reporting dashboard and data endpoints."""

import csv
import io
import json
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from app_paths import BUY_GROUPS_FILE, SALES_DATABASE, ensure_data_directory


HOST = "127.0.0.1"
PORT = 8766

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Treeco Buy Group Reporting</title>
<style>
:root{font-family:Arial,sans-serif;color:#25312d;background:#f5f6f4;--green:#154734;--gold:#d79133;--line:#d8ddd9}*{box-sizing:border-box}body{max-width:1400px;margin:0 auto;padding:24px}.header{background:var(--green);color:#fff;padding:22px 28px;border-radius:0 0 16px 16px}.header h1{font-size:32px;margin:0}.header p{margin:7px 0 0;color:#e5e5e6}.panel{background:#fff;border:1px solid var(--line);border-radius:6px;padding:22px;margin-top:20px;box-shadow:0 2px 5px #15473412}.setup{max-width:680px}.setup summary{color:var(--green);font-size:22px;font-weight:700;cursor:pointer}.setup[open] summary{margin-bottom:18px}.panel h2{color:var(--green);margin:0 0 7px;font-size:22px}.hint{color:#5d6661;margin:0 0 18px;line-height:1.45}label{display:block;font-weight:700;font-size:14px}input,select{display:block;width:100%;margin-top:7px;padding:10px;border:1px solid #b9c6be;border-radius:3px;font:14px Arial,sans-serif}.check{width:auto;display:inline;margin:0 7px 0 0;vertical-align:middle}.filter{max-width:460px}.actions{display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap}button{background:var(--green);color:#fff;border:0;border-radius:3px;padding:11px 16px;font-size:14px;font-weight:700;cursor:pointer}button.secondary{background:var(--gold);color:#25312d}button.neutral{background:#68736d;color:#fff}button.danger{background:#a62b21;color:#fff}.status{margin:14px 0 0;color:#5d6661}.success{color:#154734;font-weight:700}.error{color:#9b271c;font-weight:700}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:4px;margin-top:14px}table{border-collapse:collapse;width:100%;font-size:14px;white-space:nowrap}th,td{padding:12px;border-bottom:1px solid #e5e5e6;text-align:right}th{background:var(--green);color:#fff;text-align:left}th.num,td.num{text-align:right}td.left{text-align:left}.empty{text-align:left;color:#5d6661}
</style></head><body>
<header class="header"><h1>Buy Group Reporting</h1><p>Sales reporting by customer buy group.</p></header>
<details class="panel setup"><summary>Data files</summary><p class="hint">Uploaded files and the reporting database are stored securely with this application.</p><label>Account Number vs Buy Group CSV<input id="buy-groups-file" type="file" accept=".csv,text/csv"></label><div class="actions"><button id="upload-buy-groups">Upload mapping file</button></div><hr><label>Sales data CSV<input id="sales-file" type="file" accept=".csv,text/csv"></label><div class="actions"><button id="upload-sales">Upload sales data</button></div><div id="status" class="status"></div></details>
<section class="panel"><h2>Buy Group Report</h2><p id="loaded-sales-file" class="hint">No sales file loaded. Upload a current sales CSV to begin.</p><div class="filter"><label>Buy groups<select id="buy-groups" multiple size="8"></select></label></div><div class="filter"><label>Branches<select id="branches" multiple size="6"></select></label></div><div class="filter"><label>Filter description<input id="description-filter" type="search" placeholder="Type to filter descriptions"></label></div><label><input id="hide-zero-unit-price" class="check" type="checkbox" checked> Hide rows with unit price = 0</label><div class="actions"><button id="apply-filter">Apply filter</button></div><p class="hint">Use Ctrl or Shift to select multiple groups or branches. <strong>Unassigned</strong> includes accounts with no mapping.</p><details class="panel" style="padding:16px;margin-top:18px"><summary style="font-weight:700;cursor:pointer">Choose and order columns</summary><p class="hint" style="margin-top:12px">Move visible columns up or down to set their table and CSV order. Remove columns with the trash button; add them back from the removed list.</p><div id="column-settings"></div></details><div class="table-wrap"><table><thead id="report-head"></thead><tbody id="report"><tr><td class="empty">Loading report...</td></tr></tbody></table></div><div class="actions"><span id="table-status" class="hint" style="margin:12px 0 0"></span><button id="load-full-table" class="secondary" hidden>Load full table</button></div></section>
<section class="panel"><h2>Download Report</h2><p class="hint">Save the rows currently displayed in the table as a CSV file.</p><button id="download-report" class="secondary">Download Report CSV</button></section>
<script>
const status=document.getElementById('status'),groups=document.getElementById('buy-groups'),branches=document.getElementById('branches'),descriptionFilter=document.getElementById('description-filter'),hideZeroUnitPrice=document.getElementById('hide-zero-unit-price'),report=document.getElementById('report'),head=document.getElementById('report-head'),tableStatus=document.getElementById('table-status'),loadFullButton=document.getElementById('load-full-table'),loadedSalesFile=document.getElementById('loaded-sales-file'),columnSettings=document.getElementById('column-settings');let currentReport={headers:[],rows:[],sales_file:null},showFullTable=false,columnPreferences=[];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setStatus(message,kind=''){status.textContent=message;status.className='status '+kind}
const DEFAULT_COLUMNS=['Sales/ Material Branch','Account-Job','Name','Location','Document','Date','Item','Description','Quantity','Unit Price'];
function configureColumns(){if(columnPreferences.length===currentReport.headers.length&&columnPreferences.every(column=>currentReport.headers.includes(column.name))){renderColumnSettings();return}const defaultSet=new Set(DEFAULT_COLUMNS);columnPreferences=[...DEFAULT_COLUMNS.filter(name=>currentReport.headers.includes(name)).map(name=>({name,visible:true})),...currentReport.headers.filter(name=>!defaultSet.has(name)).map(name=>({name,visible:false}))];renderColumnSettings()}
function visibleColumns(){return columnPreferences.filter(column=>column.visible).map(column=>({name:column.name,index:currentReport.headers.indexOf(column.name)})).filter(column=>column.index>=0)}
function renderColumnSettings(){const visible=columnPreferences.filter(column=>column.visible),removed=columnPreferences.filter(column=>!column.visible);const visibleRows=visible.map((column,index)=>`<div class="actions" style="margin:8px 0"><span style="min-width:210px;font-weight:700">${esc(column.name)}</span><button class="neutral" data-move="up" data-index="${index}" title="Move ${esc(column.name)} up" aria-label="Move ${esc(column.name)} up" ${index===0?'disabled':''}>▲</button><button class="neutral" data-move="down" data-index="${index}" title="Move ${esc(column.name)} down" aria-label="Move ${esc(column.name)} down" ${index===visible.length-1?'disabled':''}>▼</button><button class="danger" data-remove="${esc(column.name)}" title="Remove ${esc(column.name)}" aria-label="Remove ${esc(column.name)}">Remove</button></div>`).join('');const removedRows=removed.length?removed.map(column=>`<div class="actions" style="margin:8px 0"><span style="min-width:210px">${esc(column.name)}</span><button class="secondary" data-add="${esc(column.name)}">Add</button></div>`).join(''):'<p class="hint">No removed columns.</p>';columnSettings.innerHTML=`<h3 style="margin:12px 0 6px">Visible columns</h3>${visibleRows}<h3 style="margin:20px 0 6px">Removed columns</h3>${removedRows}`;columnSettings.querySelectorAll('button[data-move]').forEach(button=>button.onclick=()=>{const visibleColumnsOnly=columnPreferences.filter(column=>column.visible),index=Number(button.dataset.index),next=index+(button.dataset.move==='up'?-1:1),first=visibleColumnsOnly[index],second=visibleColumnsOnly[next],firstIndex=columnPreferences.indexOf(first),secondIndex=columnPreferences.indexOf(second);[columnPreferences[firstIndex],columnPreferences[secondIndex]]=[columnPreferences[secondIndex],columnPreferences[firstIndex]];renderColumnSettings();renderTable()});columnSettings.querySelectorAll('button[data-remove]').forEach(button=>button.onclick=()=>{if(visibleColumns().length===1){setStatus('At least one column must remain visible.','error');return}columnPreferences.find(column=>column.name===button.dataset.remove).visible=false;renderColumnSettings();renderTable()});columnSettings.querySelectorAll('button[data-add]').forEach(button=>button.onclick=()=>{const index=columnPreferences.findIndex(column=>column.name===button.dataset.add),[column]=columnPreferences.splice(index,1);column.visible=true;columnPreferences.push(column);renderColumnSettings();renderTable()})}
function renderTable(){const columns=visibleColumns(),total=currentReport.rows.length,visible=showFullTable?currentReport.rows:currentReport.rows.slice(0,20);head.innerHTML=columns.length?'<tr>'+columns.map(column=>`<th>${esc(column.name)}</th>`).join('')+'</tr>':'';report.innerHTML=visible.length?visible.map(row=>'<tr>'+columns.map(column=>`<td class="left">${esc(row[column.index])}</td>`).join('')+'</tr>').join(''):`<tr><td colspan="${columns.length||1}" class="empty">No sales found for the selected filters.</td></tr>`;tableStatus.textContent=`Showing ${visible.length.toLocaleString()} out of ${total.toLocaleString()} rows`;loadFullButton.hidden=showFullTable||total<=20}
async function loadReport(){try{const selectedGroups=[...groups.selectedOptions].map(option=>option.value),selectedBranches=[...branches.selectedOptions].map(option=>option.value),query=new URLSearchParams();selectedGroups.forEach(group=>query.append('group',group));selectedBranches.forEach(branch=>query.append('branch',branch));query.set('description',descriptionFilter.value);query.set('exclude_zero_unit_price',hideZeroUnitPrice.checked?'1':'0');const response=await fetch('/api/report?'+query);const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to load report');currentReport=data;configureColumns();showFullTable=false;loadedSalesFile.textContent=data.sales_file?`Current sales file: ${data.sales_file}`:'No sales file loaded. Upload a current sales CSV to begin.';groups.innerHTML=data.groups.map(group=>`<option value="${esc(group)}" ${selectedGroups.includes(group)?'selected':''}>${esc(group)}</option>`).join('');branches.innerHTML=data.branches.map(branch=>`<option value="${esc(branch)}" ${selectedBranches.includes(branch)?'selected':''}>${esc(branch)}</option>`).join('');renderTable()}catch(error){currentReport={headers:[],rows:[],sales_file:null};head.innerHTML='';report.innerHTML=`<tr><td class="empty">${esc(error.message)}</td></tr>`;tableStatus.textContent='';loadFullButton.hidden=true;loadedSalesFile.textContent='Unable to load sales data.'}}
async function upload(fileId,path,label){const file=document.getElementById(fileId).files[0];if(!file){setStatus(`Choose the ${label} CSV first.`,'error');return}try{setStatus(`Saving ${label}...`);const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contents:await file.text(),filename:file.name})});const data=await response.json();if(!response.ok)throw Error(data.error||'Upload failed');setStatus(data.message,'success');await loadReport()}catch(error){setStatus(error.message,'error')}}
document.getElementById('upload-buy-groups').onclick=()=>upload('buy-groups-file','/api/buy-groups','Account Number vs Buy Group');document.getElementById('upload-sales').onclick=()=>upload('sales-file','/api/sales','sales data');document.getElementById('apply-filter').onclick=loadReport;descriptionFilter.addEventListener('input',loadReport);hideZeroUnitPrice.addEventListener('change',loadReport);loadFullButton.onclick=()=>{showFullTable=true;renderTable()};document.getElementById('download-report').onclick=()=>{try{if(!currentReport.rows.length)throw Error('There are no displayed rows to download.');const columns=visibleColumns();if(!columns.length)throw Error('Choose at least one column to download.');const quote=value=>'"'+String(value??'').replace(/"/g,'""')+'"';const itemIndex=currentReport.headers.indexOf('Item');const excelSku=value=>'="'+String(value??'').replace(/"/g,'""')+'"';const exportRows=currentReport.rows.map(row=>columns.map(column=>column.index===itemIndex?excelSku(row[column.index]):row[column.index]));const csv=[columns.map(column=>column.name),...exportRows].map(row=>row.map(quote).join(',')).join('\r\n');const selectedGroups=[...groups.selectedOptions].map(option=>option.value);const filenamePart=value=>String(value).trim().replace(/[<>:"/\\|?*]+/g,' ').replace(/\s+/g,' ').trim().slice(0,80);const groupPart=selectedGroups.length?selectedGroups.map(filenamePart).filter(Boolean).join(' + '):'All Buy Groups';const descriptionPart=filenamePart(descriptionFilter.value)||'All Descriptions';const filename=`buy_group_report - ${groupPart} - ${descriptionPart}.csv`;const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));link.download=filename;link.click();URL.revokeObjectURL(link.href)}catch(error){setStatus(error.message,'error')}};loadReport();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        if request.path == "/":
            self.text(200, PAGE, "text/html; charset=utf-8")
        elif request.path == "/api/report":
            try:
                query = parse_qs(request.query)
                self.json(200, report(query.get("group", []), query.get("branch", []), query.get("description", [""])[0], query.get("exclude_zero_unit_price", ["0"])[0] == "1"))
            except Exception as error:
                self.json(400, {"error": str(error)})
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/buy-groups", "/api/sales"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            contents = str(payload["contents"])
            if path == "/api/buy-groups":
                rows = save_buy_groups(contents)
                message = f"Saved {rows:,} mappings to the local data folder."
            else:
                rows = save_sales(contents, str(payload.get("filename", "sales.csv")))
                message = f"Imported {rows:,} sales rows into the local reporting database."
            self.json(200, {"rows": rows, "message": message})
        except Exception as error:
            self.json(400, {"error": str(error)})

    def text(self, status, content, content_type):
        body = content.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def json(self, status, data):
        self.text(status, json.dumps(data), "application/json; charset=utf-8")

    def log_message(self, *_args):
        return


SALES_HEADERS = ["Document", "Inv Type", "Account", "Name", "Job", "Sales/ Material Branch", "Date", "Accounting Year", "Accounting Period", "Item Ext Price", "Item Ext Cost", "Invoice GM", "Item", "Description", "Quantity", "Unit Price", "Unitcost", "Item GM"]
SALES_COLUMNS = set(SALES_HEADERS)
REPORT_HEADERS = SALES_HEADERS + ["Account-Job", "Location"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS import_batches (id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, imported_at TEXT NOT NULL, row_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, import_batch_id INTEGER NOT NULL REFERENCES import_batches(id), document TEXT NOT NULL, invoice_type TEXT, account_number TEXT NOT NULL, customer_name TEXT, job TEXT, sales_material_branch TEXT, sale_date TEXT, accounting_year INTEGER, accounting_period INTEGER, item_ext_price REAL, item_ext_cost REAL, invoice_gm REAL, item TEXT, description TEXT, quantity REAL, unit_price REAL, unit_cost REAL, item_gm REAL, raw_data TEXT);
CREATE INDEX IF NOT EXISTS idx_sales_account ON sales(account_number);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
"""


def clean(value): return value.strip() if value is not None else ""
def numeric(value, kind=float):
    value = clean(value)
    return None if not value else kind(value)


def buy_group_mapping():
    if not BUY_GROUPS_FILE.exists(): return {}
    with BUY_GROUPS_FILE.open(encoding="utf-8-sig", newline="") as file:
        return {
            clean(row["Account Number"]): (
                clean(row["Buy Group"]) or "Unassigned",
                clean(row.get("City")),
            )
            for row in csv.DictReader(file)
            if clean(row.get("Account Number"))
        }


def branch_code(value):
    """Use the first four-digit branch where a sales row lists multiple branches."""
    value = clean(value)
    return value[:4] if len(value) >= 4 and value[:4].isdigit() else value


def account_job_key(account, job):
    """Return the mapping key used for a sales account and its ship-to job."""
    account, job = clean(account), clean(job)
    return f"{account}~{job}" if account and job else account


def report(selected_groups, selected_branches, description_filter="", exclude_zero_unit_price=False):
    mapping = buy_group_mapping()
    groups = sorted({group for group, _location in mapping.values()} | {"Unassigned"})
    if not SALES_DATABASE.exists(): return {"groups": groups, "branches": [], "headers": REPORT_HEADERS, "rows": [], "sales_file": None}
    with sqlite3.connect(SALES_DATABASE) as database:
        database.row_factory = sqlite3.Row
        columns = {row[1] for row in database.execute("PRAGMA table_info(sales)")}
        if "raw_data" not in columns: return {"groups": groups, "branches": [], "headers": REPORT_HEADERS, "rows": [], "sales_file": None}
        rows = database.execute("SELECT raw_data FROM sales WHERE raw_data IS NOT NULL ORDER BY id").fetchall()
        import_row = database.execute("SELECT source_file FROM import_batches ORDER BY id DESC LIMIT 1").fetchone()
    branches = sorted({branch_code(json.loads(row["raw_data"])["Sales/ Material Branch"]) for row in rows if branch_code(json.loads(row["raw_data"])["Sales/ Material Branch"])})
    result = []
    description_filter = description_filter.strip().casefold()
    for row in rows:
        raw = json.loads(row["raw_data"])
        account = clean(raw["Account"])
        group, location = mapping.get(
            account_job_key(account, raw["Job"]),
            mapping.get(account, ("Unassigned", "")),
        )
        if selected_groups and group not in selected_groups: continue
        if selected_branches and branch_code(raw["Sales/ Material Branch"]) not in selected_branches: continue
        if description_filter not in raw["Description"].casefold(): continue
        if exclude_zero_unit_price and is_zero_unit_price(raw["Unit Price"]): continue
        result.append([raw[header] for header in SALES_HEADERS] + [f"{raw['Account']}-{raw['Job']}", location])
    result.sort(key=lambda row: account_sort_key(row[SALES_HEADERS.index("Account")]))
    return {"groups": groups, "branches": branches, "headers": REPORT_HEADERS, "rows": result, "sales_file": import_row["source_file"] if import_row else None}


def is_zero_unit_price(value):
    try:
        return float(clean(value).replace(",", "")) == 0
    except ValueError:
        return False


def account_sort_key(value):
    value = clean(value)
    try:
        return (0, int(value))
    except ValueError:
        return (1, value.casefold())


def save_buy_groups(contents):
    reader = csv.DictReader(io.StringIO(contents))
    if not reader.fieldnames or not {"Buy Group", "Account Number"}.issubset(reader.fieldnames): raise ValueError("The CSV must include 'Buy Group' and 'Account Number' columns.")
    rows = sum(1 for row in reader if clean(row.get("Account Number")))
    if not rows: raise ValueError("The CSV does not contain any account mappings.")
    ensure_data_directory(); BUY_GROUPS_FILE.write_text(contents, encoding="utf-8-sig", newline="")
    return rows


def save_sales(contents, filename):
    reader = csv.DictReader(io.StringIO(contents))
    if not reader.fieldnames or not SALES_COLUMNS.issubset(reader.fieldnames): raise ValueError("The CSV is missing one or more required sales-data columns.")
    rows = []
    for row in reader:
        date = clean(row["Date"]); sale_date = datetime.strptime(date, "%m/%d/%Y %H:%M:%S").date().isoformat() if date else None
        raw = {header: row.get(header, "") for header in SALES_HEADERS}
        rows.append((clean(row["Document"]), clean(row["Inv Type"]), clean(row["Account"]), clean(row["Name"]), clean(row["Job"]), clean(row["Sales/ Material Branch"]), sale_date, numeric(row["Accounting Year"], int), numeric(row["Accounting Period"], int), numeric(row["Item Ext Price"]), numeric(row["Item Ext Cost"]), numeric(row["Invoice GM"]), clean(row["Item"]), clean(row["Description"]), numeric(row["Quantity"]), numeric(row["Unit Price"]), numeric(row["Unitcost"]), numeric(row["Item GM"]), json.dumps(raw)))
    if not rows: raise ValueError("The CSV does not contain any sales rows.")
    ensure_data_directory()
    with sqlite3.connect(SALES_DATABASE) as database:
        database.executescript(SCHEMA)
        columns = {row[1] for row in database.execute("PRAGMA table_info(sales)")}
        if "raw_data" not in columns:
            database.execute("ALTER TABLE sales ADD COLUMN raw_data TEXT")
        # This is a monthly report: every sales upload replaces the prior period.
        database.execute("DELETE FROM sales")
        database.execute("DELETE FROM import_batches")
        batch = database.execute("INSERT INTO import_batches(source_file, imported_at, row_count) VALUES (?, ?, ?)", (filename, datetime.now().astimezone().isoformat(timespec="seconds"), len(rows)))
        database.executemany("INSERT INTO sales(import_batch_id, document, invoice_type, account_number, customer_name, job, sales_material_branch, sale_date, accounting_year, accounting_period, item_ext_price, item_ext_cost, invoice_gm, item, description, quantity, unit_price, unit_cost, item_gm, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(batch.lastrowid, *row) for row in rows])
    return len(rows)
