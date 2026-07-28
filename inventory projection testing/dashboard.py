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
from database import clear_imported_data, engine, replace_imported_data
from importer import (
    load_spruce_single_branch_stock,
    load_spruce_single_branch_usage,
    load_spruce_stock,
    load_spruce_usage,
)
from metrics import build_inventory_projection
from orders import build_order_export
from vendors import load_vendor_names


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
<section class="panel"><h2 style="margin-top:0;font-size:18px">Import Spruce reports</h2><details class="panel" style="margin:0 0 14px;padding:12px;background:#f7fafc"><summary><b>Import help</b></summary><ul style="margin:10px 0 0;padding-left:20px"><li><b>Multi-branch reports (detailed consolidation):</b> Upload the Stock Status and 12-month Usage reports that include all required branch detail. Leave Single-branch report format unchecked.</li><li><b>Single-branch reports:</b> Upload reports generated for one branch only, check Single-branch report format, then select the branch that produced the reports.</li></ul></details><div class="grid import"><label>Stock Status CSV<input id="stock-file" type="file" accept=".csv"></label><label>12-month Usage CSV<input id="usage-file" type="file" accept=".csv"></label><div><button id="import">Process and save reports</button><button id="open-data-folder" class="secondary" style="margin-left:8px">Open data folder</button><button id="clear-database" class="secondary" style="margin:8px 0 0">Clear imported data</button></div></div><div class="actions" style="margin-top:12px"><label><input id="single-branch" class="check" type="checkbox"> Single-branch report format</label><label style="min-width:260px">Single-report branch<select id="import-branch" style="height:auto;margin-top:4px"></select></label></div><div class="hint" style="margin-top:8px">Imported data is used only for the current application session.</div><div id="import-status"></div></section>
<section class="panel"><h2 style="margin-top:0;font-size:18px">Filters</h2><div class="grid"><label>Branches<select id="branches" multiple></select></label><label>Vendors<select id="vendors" multiple></select></label><label>SKU or description<input id="search" placeholder="Search items"></label><label>Options<br><span style="display:inline-block;margin-top:12px"><input id="inactive" class="check" type="checkbox"> Show inactive items</span></label></div></section>
<section class="panel"><div class="actions"><button id="select-recommended">Select recommended (filtered)</button><button id="clear-selection" class="secondary">Clear selection</button><span id="summary" class="summary">0 selected orders · 0 units</span></div><div id="load-error" class="error"></div><div class="table-wrap" style="margin-top:14px"><table id="inventory-table"><thead><tr><th data-sort="order_selected">Order?</th><th class="left" data-sort="sku">SKU</th><th class="left" data-sort="description">Description</th><th data-sort="vendor">Vendor</th><th data-sort="branch_id">Branch</th><th class="left" data-sort="branch_name">Branch name</th><th data-sort="on_hand">On hand</th><th data-sort="on_order">On order</th><th data-sort="available">Available</th><th data-sort="last_12_month_sales">12-month sales</th><th data-sort="avg_daily_sales">Avg. daily sales</th><th data-sort="projected_days_remaining">Projected days</th><th data-sort="recommended_order_qty">Recommended</th><th data-sort="order_amount">Order amount</th></tr></thead><tbody id="inventory"></tbody></table></div></section>
<section class="panel"><div class="actions"><h2 style="margin:0;font-size:18px">Purchase-order preview</h2><button id="download" class="secondary">Download consolidated order CSV</button></div><div id="preview-empty" class="hint" style="margin-top:12px">Select one or more order lines to preview the consolidated order.</div><div id="preview-wrap" class="table-wrap hidden" style="margin-top:12px"><table id="preview"></table></div></section>
<script>
const $=id=>document.getElementById(id);let rows=[],branches={},configuredBranches={},vendors={},selected=new Set(),amounts={},sortKey=null,sortAscending=true;const hasDesktopApi=()=>Boolean(window.pywebview&&window.pywebview.api&&typeof window.pywebview.api.save_order_csv==="function");
const key=r=>r.sku+"|"+r.branch_id,esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])),num=v=>Number(v||0),fmt=v=>num(v).toLocaleString(undefined,{maximumFractionDigits:0}),dec=v=>num(v).toLocaleString(undefined,{maximumFractionDigits:3});
async function api(path,body){let response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});let data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.error||"Request failed");return data}
function branchIds(){return [...$("branches").selectedOptions].map(o=>o.value)}
function vendorIds(){return [...$("vendors").selectedOptions].map(o=>o.value)}
function visible(){let ids=new Set(branchIds()),vendorIdsSet=new Set(vendorIds()),search=$("search").value.trim().toLowerCase(),inactive=$("inactive").checked;return rows.filter(r=>ids.has(String(r.branch_id))&&vendorIdsSet.has(String(r.vendor||""))&&(!search||String(r.sku).toLowerCase().includes(search)||String(r.description).toLowerCase().includes(search))&&(inactive||!(num(r.on_hand)===0&&num(r.last_12_month_sales)===0)))}
function sortValue(row,column){if(column==="order_selected")return selected.has(key(row))?1:0;if(column==="order_amount")return amounts[key(row)]??num(row.recommended_order_qty);return row[column]}
function sortedVisible(){let numeric=new Set(["order_selected","order_amount","on_hand","on_order","available","last_12_month_sales","avg_daily_sales","projected_days_remaining","recommended_order_qty"]);return visible().slice().sort((left,right)=>{if(!sortKey)return 0;let a=sortValue(left,sortKey),b=sortValue(right,sortKey);if(a==null)return 1;if(b==null)return -1;let result=numeric.has(sortKey)?num(a)-num(b):String(a).localeCompare(String(b));return sortAscending?result:-result})}
function updateSortHeaders(){document.querySelectorAll("#inventory-table th[data-sort]").forEach(header=>{let label=header.dataset.label||(header.dataset.label=header.textContent);header.textContent=label+(header.dataset.sort===sortKey?(sortAscending?" ↑":" ↓"):"")})}
function render(){let html="";sortedVisible().forEach(r=>{let k=key(r),amount=amounts[k]??num(r.recommended_order_qty);html+="<tr><td><input class='check select' data-key='"+esc(k)+"' type='checkbox' "+(selected.has(k)?"checked":"")+"></td><td class='left'>"+esc(r.sku)+"</td><td class='left'>"+esc(r.description)+"</td><td>"+esc(r.vendor||"")+"</td><td>"+esc(r.branch_id)+"</td><td class='left'>"+esc(r.branch_name)+"</td><td>"+fmt(r.on_hand)+"</td><td>"+fmt(r.on_order)+"</td><td>"+fmt(r.available)+"</td><td>"+fmt(r.last_12_month_sales)+"</td><td>"+dec(r.avg_daily_sales)+"</td><td>"+(r.projected_days_remaining==null?"—":dec(r.projected_days_remaining))+"</td><td>"+fmt(r.recommended_order_qty)+"</td><td><input class='qty amount' data-key='"+esc(k)+"' type='number' min='0' step='1' value='"+amount+"'></td></tr>"});$("inventory").innerHTML=html;document.querySelectorAll(".select").forEach(x=>x.onchange=()=>{x.checked?selected.add(x.dataset.key):selected.delete(x.dataset.key);preview()});document.querySelectorAll(".amount").forEach(x=>x.onchange=()=>{let amount=Math.max(0,num(x.value));amounts[x.dataset.key]=amount;amount>0?selected.add(x.dataset.key):selected.delete(x.dataset.key);render()});updateSortHeaders();preview()}
function chosen(){let ids=branchIds();return rows.filter(r=>selected.has(key(r))).map(r=>Object.assign({},r,{order_amount:amounts[key(r)]??num(r.recommended_order_qty)})).filter(r=>num(r.order_amount)>0&&ids.includes(String(r.branch_id)))}
function preview(){let items=chosen(),total=items.reduce((s,r)=>s+num(r.order_amount),0);$("summary").textContent=items.length+" selected orders · "+fmt(total)+" units";if(!items.length){$("preview-empty").classList.remove("hidden");$("preview-wrap").classList.add("hidden");return}let ids=branchIds(),groups={};items.forEach(r=>{let k=r.sku+"|"+r.description,e=groups[k]||{sku:r.sku,description:r.description,total:0};e[r.branch_id]=(e[r.branch_id]||0)+num(r.order_amount);e.total+=num(r.order_amount);groups[k]=e});let head="<thead><tr><th class='left'>Item</th><th class='left'>Description</th><th>Total order</th>";ids.forEach(id=>head+="<th>Branch "+esc(id)+" ("+esc(branches[id]).toLowerCase()+")</th>");head+="</tr></thead><tbody>";Object.values(groups).forEach(r=>{head+="<tr><td class='left'>"+esc(r.sku)+"</td><td class='left'>"+esc(r.description)+"</td><td>"+fmt(r.total)+"</td>";ids.forEach(id=>head+="<td>"+fmt(r[id])+"</td>");head+="</tr>"});$("preview").innerHTML=head+"</tbody>";$("preview-empty").classList.add("hidden");$("preview-wrap").classList.remove("hidden")}
function status(id,message,kind){let e=$(id);e.textContent=message;e.className=kind||""}
async function load(){try{let data=await api("/api/state");rows=data.rows;branches=data.branches;configuredBranches=data.configured_branches;vendors=data.vendors;["stock_target_days","vendor_lead_time_days","buffer_days"].forEach(n=>$(n).value=data.settings[n]);$("branches").innerHTML=Object.entries(branches).map(x=>"<option value='"+esc(x[0])+"' selected>"+esc(x[0])+" — "+esc(x[1])+"</option>").join("");$("import-branch").innerHTML=Object.entries(configuredBranches).map(x=>"<option value='"+esc(x[0])+"'>"+esc(x[0])+" — "+esc(x[1])+"</option>").join("");let used=[...new Set(rows.map(r=>String(r.vendor||"")))].sort((a,b)=>String(vendors[a]||a).localeCompare(String(vendors[b]||b)));$("vendors").innerHTML=used.map(code=>"<option value='"+esc(code)+"' selected>"+esc(code?code+" — ":"")+" "+esc(vendors[code]||(code?"Unknown vendor":"No vendor assigned"))+"</option>").join("");$("load-error").textContent="";render()}catch(error){$("load-error").textContent=error.message}}
["branches","vendors","search","inactive"].forEach(id=>$(id).addEventListener("input",render));
document.querySelectorAll("#inventory-table th[data-sort]").forEach(header=>header.onclick=()=>{let column=header.dataset.sort;if(sortKey===column)sortAscending=!sortAscending;else{sortKey=column;sortAscending=true}render()});
$("select-recommended").onclick=()=>{visible().filter(r=>num(r.recommended_order_qty)>0).forEach(r=>selected.add(key(r)));render()};$("clear-selection").onclick=()=>{selected.clear();amounts={};render()};
$("save-settings").onclick=async()=>{try{let settings={};["stock_target_days","vendor_lead_time_days","buffer_days"].forEach(n=>settings[n]=num($(n).value));await api("/api/settings",settings);status("settings-status","Settings saved.","success");await load()}catch(error){status("settings-status",error.message,"error")}};
$("import").onclick=async()=>{let stock=$("stock-file").files[0],usage=$("usage-file").files[0];if(!stock||!usage){status("import-status","Select both report files first.","error");return}let button=$("import"),singleBranch=$("single-branch").checked;button.disabled=true;status("import-status","Importing reports…","status");try{await api("/api/import",{stock_csv:await stock.text(),usage_csv:await usage.text(),single_branch:singleBranch,branch_id:$("import-branch").value});selected.clear();amounts={};status("import-status","Reports processed and saved.","success");await load()}catch(error){status("import-status",error.message,"error")}finally{button.disabled=false}};
$("open-data-folder").onclick=async()=>{try{if(!hasDesktopApi()||typeof window.pywebview.api.open_data_folder!=="function")throw Error("The desktop folder action is not ready. Rebuild and reinstall the updated application.");await window.pywebview.api.open_data_folder()}catch(error){status("import-status",error.message,"error")}};
$("clear-database").onclick=async()=>{if(!confirm("Clear all imported inventory and usage data for this session?"))return;try{await api("/api/clear-database",{});selected.clear();amounts={};$("inventory").innerHTML="";preview();status("import-status","Imported data cleared. Upload new Spruce reports to continue.","success")}catch(error){status("import-status",error.message,"error")}};
$("download").onclick=async()=>{let items=chosen();if(!items.length)return;try{if(!hasDesktopApi())throw Error("The desktop save dialog is not ready. Rebuild and reinstall the updated application, then try again.");let response=await fetch("/api/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items:items,branch_ids:branchIds()})});if(!response.ok){let data=await response.json();throw Error(data.error||"Export failed")}let saved=await window.pywebview.api.save_order_csv(await response.text());status("load-error",saved?"Order saved to: "+saved:"Save cancelled.","success")}catch(error){$("load-error").textContent=error.message}};
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            configured_branches = load_branches()
            try:
                data = projection()
                active_branch_ids = data["branch_id"].astype(str).drop_duplicates()
                active_branches = {
                    branch_id: configured_branches.get(
                        branch_id,
                        data.loc[data["branch_id"].astype(str).eq(branch_id), "branch_name"].iloc[0],
                    )
                    for branch_id in active_branch_ids
                }
                self.json(200, {
                    "settings": load_settings(),
                    "branches": active_branches,
                    "configured_branches": configured_branches,
                    "vendors": load_vendor_names(),
                    "rows": json.loads(data.to_json(orient="records")),
                })
            except Exception as error:
                self.json(200, {
                    "settings": load_settings(),
                    "branches": configured_branches,
                    "configured_branches": configured_branches,
                    "vendors": load_vendor_names(),
                    "rows": [],
                    "message": f"Upload Spruce reports to begin: {error}",
                })
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
                if payload.get("single_branch"):
                    branch_id = str(payload.get("branch_id", ""))
                    inventory = load_spruce_single_branch_stock(
                        io.StringIO(stock), branch_id
                    )
                    usage_data = load_spruce_single_branch_usage(
                        io.StringIO(usage), branch_id
                    )
                else:
                    inventory = load_spruce_stock(io.StringIO(stock))
                    usage_data = load_spruce_usage(io.StringIO(usage))
                if inventory.empty or usage_data.empty:
                    raise ValueError("Both reports must contain valid data rows.")
                replace_imported_data(inventory, usage_data)
                archive_report(stock, "stock")
                archive_report(usage, "usage")
                self.json(200, {"inventory_rows": len(inventory), "usage_rows": len(usage_data)})
                return
            if path == "/api/clear-database":
                clear_imported_data()
                self.json(200, {"cleared": True})
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
