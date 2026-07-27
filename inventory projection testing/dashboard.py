"""Local HTML dashboard for the Spruce inventory reorder tool."""

import io
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

import pandas as pd

from app_paths import IMPORT_DIR, ensure_data_directories
from branches import load_branches
from config import load_settings, save_settings
from database import engine, replace_imported_data
from importer import load_spruce_stock, load_spruce_usage
from metrics import build_inventory_projection
from orders import build_order_export


HOST = "127.0.0.1"
PORT = 8765


def projection():
    inventory = pd.read_sql("SELECT * FROM inventory", engine)
    usage = pd.read_sql("SELECT * FROM usage_history", engine)
    return build_inventory_projection(
        inventory, usage, load_settings(), include_inactive=True
    )


def archive_report(contents, report_name):
    ensure_data_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (IMPORT_DIR / f"{timestamp}_{report_name}.csv").write_text(
        contents, encoding="utf-8"
    )


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spruce Inventory Reorder Tool</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#1d2733;background:#f4f7f9}body{max-width:1600px;margin:0 auto;padding:26px}.panel{background:#fff;border:1px solid #dde4e8;border-radius:10px;padding:18px;margin:16px 0;box-shadow:0 1px 3px #172b4d0d}h1{margin:0 0 2px;font-size:28px}.hint,.status{color:#66747f}.grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;align-items:end}.settings{grid-template-columns:repeat(3,minmax(160px,1fr)) auto}.import{grid-template-columns:1fr 1fr auto}.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}label{font-weight:650;font-size:14px;display:block}input,select{box-sizing:border-box;width:100%;margin-top:6px;padding:9px;border:1px solid #b9c6ce;border-radius:6px;background:#fff;font:14px inherit}select{height:96px}button{background:#1769e0;color:#fff;border:0;border-radius:6px;padding:10px 15px;font:600 14px inherit;cursor:pointer}button.secondary{background:#e8eef2;color:#23313d}button:disabled{opacity:.55}.error{color:#b42318;margin-top:10px;white-space:pre-wrap}.success{color:#137333;margin-top:10px}.table-wrap{overflow:auto;max-height:570px;border:1px solid #dde4e8;border-radius:7px}table{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}th,td{padding:8px 9px;border-bottom:1px solid #e6ebee;text-align:right}th{position:sticky;top:0;background:#edf3f6;z-index:1;font-weight:700}th.left,td.left{text-align:left}tbody tr:hover{background:#f7fafc}.qty{width:82px;margin:0;padding:5px;text-align:right}.check{width:auto;margin:0;transform:scale(1.1)}.summary{font-weight:650;margin-left:auto}.hidden{display:none}@media(max-width:900px){.grid,.settings,.import{grid-template-columns:1fr 1fr}.summary{margin-left:0}}
</style></head><body>
<h1>ECI Spruce Inventory Reorder Tool</h1><div class="hint">Import reports, review branch-level recommendations, then export a consolidated order.</div>
<section class="panel"><details><summary><b>Reorder settings</b></summary><div class="grid settings" style="margin-top:12px"><label>Stock target (days)<input id="stock_target_days" type="number" min="0" step="1"></label><label>Vendor lead time (days)<input id="vendor_lead_time_days" type="number" min="0" step="1"></label><label>Buffer time (days)<input id="buffer_days" type="number" min="0" step="1"></label><button id="save-settings">Save settings</button></div><div id="settings-status" class="status"></div></details></section>
<section class="panel"><h2 style="margin-top:0;font-size:18px">Import Spruce reports</h2><div class="grid import"><label>Stock Status CSV<input id="stock-file" type="file" accept=".csv"></label><label>12-month Usage CSV<input id="usage-file" type="file" accept=".csv"></label><button id="import">Process and save reports</button></div><div class="hint" style="margin-top:8px">A backup of the previous database and copies of both reports are kept in the data folder.</div><div id="import-status"></div></section>
<section class="panel"><h2 style="margin-top:0;font-size:18px">Filters</h2><div class="grid"><label>Branches<select id="branches" multiple></select></label><label>Vendor<input id="vendor" placeholder="Vendor code"></label><label>SKU or description<input id="search" placeholder="Search items"></label><label>Options<br><span style="display:inline-block;margin-top:12px"><input id="inactive" class="check" type="checkbox"> Show inactive items</span></label></div></section>
<section class="panel"><div class="actions"><button id="select-recommended">Select visible recommended</button><button id="clear-selection" class="secondary">Clear selection</button><span id="summary" class="summary">0 selected orders · 0 units</span></div><div id="load-error" class="error"></div><div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Order?</th><th class="left">SKU</th><th class="left">Description</th><th>Vendor</th><th>Branch</th><th class="left">Branch name</th><th>On hand</th><th>On order</th><th>Available</th><th>12-month sales</th><th>Avg. daily sales</th><th>Projected days</th><th>Recommended</th><th>Order amount</th></tr></thead><tbody id="inventory"></tbody></table></div></section>
<section class="panel"><div class="actions"><h2 style="margin:0;font-size:18px">Purchase-order preview</h2><button id="download" class="secondary">Download consolidated order CSV</button></div><div id="preview-empty" class="hint" style="margin-top:12px">Select one or more order lines to preview the consolidated order.</div><div id="preview-wrap" class="table-wrap hidden" style="margin-top:12px"><table id="preview"></table></div></section>
<script>
const $=id=>document.getElementById(id);let rows=[],branches={},selected=new Set(),amounts={};
const key=r=>r.sku+"|"+r.branch_id,esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])),num=v=>Number(v||0),fmt=v=>num(v).toLocaleString(undefined,{maximumFractionDigits:0}),dec=v=>num(v).toLocaleString(undefined,{maximumFractionDigits:3});
async function api(path,body){let response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});let data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.error||"Request failed");return data}
function branchIds(){return [...$("branches").selectedOptions].map(o=>o.value)}
function visible(){let ids=new Set(branchIds()),vendor=$("vendor").value.trim().toLowerCase(),search=$("search").value.trim().toLowerCase(),inactive=$("inactive").checked;return rows.filter(r=>ids.has(String(r.branch_id))&&(!vendor||String(r.vendor||"").toLowerCase().includes(vendor))&&(!search||String(r.sku).toLowerCase().includes(search)||String(r.description).toLowerCase().includes(search))&&(inactive||!(num(r.on_hand)===0&&num(r.last_12_month_sales)===0)))}
function render(){let html="";visible().forEach(r=>{let k=key(r),amount=amounts[k]??num(r.recommended_order_qty);html+="<tr><td><input class='check select' data-key='"+esc(k)+"' type='checkbox' "+(selected.has(k)?"checked":"")+"></td><td class='left'>"+esc(r.sku)+"</td><td class='left'>"+esc(r.description)+"</td><td>"+esc(r.vendor||"")+"</td><td>"+esc(r.branch_id)+"</td><td class='left'>"+esc(r.branch_name)+"</td><td>"+fmt(r.on_hand)+"</td><td>"+fmt(r.on_order)+"</td><td>"+fmt(r.available)+"</td><td>"+fmt(r.last_12_month_sales)+"</td><td>"+dec(r.avg_daily_sales)+"</td><td>"+(r.projected_days_remaining==null?"—":dec(r.projected_days_remaining))+"</td><td>"+fmt(r.recommended_order_qty)+"</td><td><input class='qty amount' data-key='"+esc(k)+"' type='number' min='0' step='1' value='"+amount+"'></td></tr>"});$("inventory").innerHTML=html;document.querySelectorAll(".select").forEach(x=>x.onchange=()=>{x.checked?selected.add(x.dataset.key):selected.delete(x.dataset.key);preview()});document.querySelectorAll(".amount").forEach(x=>x.onchange=()=>{amounts[x.dataset.key]=Math.max(0,num(x.value));preview()});preview()}
function chosen(){let ids=branchIds();return rows.filter(r=>selected.has(key(r))).map(r=>Object.assign({},r,{order_amount:amounts[key(r)]??num(r.recommended_order_qty)})).filter(r=>num(r.order_amount)>0&&ids.includes(String(r.branch_id)))}
function preview(){let items=chosen(),total=items.reduce((s,r)=>s+num(r.order_amount),0);$("summary").textContent=items.length+" selected orders · "+fmt(total)+" units";if(!items.length){$("preview-empty").classList.remove("hidden");$("preview-wrap").classList.add("hidden");return}let ids=branchIds(),groups={};items.forEach(r=>{let k=r.sku+"|"+r.description,e=groups[k]||{sku:r.sku,description:r.description,total:0};e[r.branch_id]=(e[r.branch_id]||0)+num(r.order_amount);e.total+=num(r.order_amount);groups[k]=e});let head="<thead><tr><th class='left'>Item</th><th class='left'>Description</th><th>Total order</th>";ids.forEach(id=>head+="<th>Branch "+esc(id)+" ("+esc(branches[id]).toLowerCase()+")</th>");head+="</tr></thead><tbody>";Object.values(groups).forEach(r=>{head+="<tr><td class='left'>"+esc(r.sku)+"</td><td class='left'>"+esc(r.description)+"</td><td>"+fmt(r.total)+"</td>";ids.forEach(id=>head+="<td>"+fmt(r[id])+"</td>");head+="</tr>"});$("preview").innerHTML=head+"</tbody>";$("preview-empty").classList.add("hidden");$("preview-wrap").classList.remove("hidden")}
function status(id,message,kind){let e=$(id);e.textContent=message;e.className=kind||""}
async function load(){try{let data=await api("/api/state");rows=data.rows;branches=data.branches;["stock_target_days","vendor_lead_time_days","buffer_days"].forEach(n=>$(n).value=data.settings[n]);$("branches").innerHTML=Object.entries(branches).map(x=>"<option value='"+esc(x[0])+"' selected>"+esc(x[0])+" — "+esc(x[1])+"</option>").join("");$("load-error").textContent="";render()}catch(error){$("load-error").textContent=error.message}}
["branches","vendor","search","inactive"].forEach(id=>$(id).addEventListener("input",render));
$("select-recommended").onclick=()=>{visible().filter(r=>num(r.recommended_order_qty)>0).forEach(r=>selected.add(key(r)));render()};$("clear-selection").onclick=()=>{selected.clear();amounts={};render()};
$("save-settings").onclick=async()=>{try{let settings={};["stock_target_days","vendor_lead_time_days","buffer_days"].forEach(n=>settings[n]=num($(n).value));await api("/api/settings",settings);status("settings-status","Settings saved.","success");await load()}catch(error){status("settings-status",error.message,"error")}};
$("import").onclick=async()=>{let stock=$("stock-file").files[0],usage=$("usage-file").files[0];if(!stock||!usage){status("import-status","Select both report files first.","error");return}let button=$("import");button.disabled=true;status("import-status","Importing reports…","status");try{await api("/api/import",{stock_csv:await stock.text(),usage_csv:await usage.text()});selected.clear();amounts={};status("import-status","Reports processed and saved.","success");await load()}catch(error){status("import-status",error.message,"error")}finally{button.disabled=false}};
$("download").onclick=async()=>{let items=chosen();if(!items.length)return;try{let response=await fetch("/api/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items:items,branch_ids:branchIds()})});if(!response.ok){let data=await response.json();throw Error(data.error||"Export failed")}let blob=await response.blob(),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="purchase_order_draft.csv";link.click();URL.revokeObjectURL(link.href)}catch(error){$("load-error").textContent=error.message}};
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            try:
                data = projection()
                self.json(200, {
                    "settings": load_settings(),
                    "branches": load_branches(),
                    "rows": json.loads(data.to_json(orient="records")),
                })
            except Exception as error:
                self.json(400, {"error": f"Unable to load imported data: {error}"})
            return
        if path == "/":
            self.text(200, PAGE, "text/html; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.payload()
            if path == "/api/settings":
                save_settings(payload)
                self.json(200, {"saved": True})
                return
            if path == "/api/import":
                stock = str(payload["stock_csv"])
                usage = str(payload["usage_csv"])
                inventory = load_spruce_stock(io.StringIO(stock))
                usage_data = load_spruce_usage(io.StringIO(usage))
                if inventory.empty or usage_data.empty:
                    raise ValueError("Both reports must contain valid data rows.")
                replace_imported_data(inventory, usage_data)
                archive_report(stock, "stock")
                archive_report(usage, "usage")
                self.json(200, {"inventory_rows": len(inventory), "usage_rows": len(usage_data)})
                return
            if path == "/api/export":
                items = pd.DataFrame(payload.get("items", []))
                branch_ids = [str(value) for value in payload.get("branch_ids", [])]
                if items.empty or not branch_ids:
                    raise ValueError("Select at least one order line and branch.")
                export = build_order_export(items, branch_ids)
                self.text(200, export.to_csv(index=False), "text/csv; charset=utf-8",
                          "attachment; filename=purchase_order_draft.csv")
                return
            self.send_error(404)
        except Exception as error:
            self.json(400, {"error": str(error)})

    def payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length))

    def json(self, status, data):
        self.text(status, json.dumps(data), "application/json; charset=utf-8")

    def text(self, status, text, content_type, disposition=None):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return
