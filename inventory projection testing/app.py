import pandas as pd
import streamlit as st

from app_paths import IMPORT_DIR, ensure_data_directories
from branches import load_branches
from config import load_settings, save_settings
from database import engine
from database import replace_imported_data
from importer import load_spruce_stock, load_spruce_usage
from metrics import build_inventory_projection


st.set_page_config(page_title="Spruce Reorder Tool", layout="wide")


def load_projection(settings, include_inactive):
    try:
        inventory = pd.read_sql("SELECT * FROM inventory", engine)
        usage_history = pd.read_sql("SELECT * FROM usage_history", engine)
    except Exception as error:
        st.error("No imported inventory data is available yet.")
        st.info("Upload a Stock Status CSV and a 12-month Usage CSV in the sidebar.")
        st.caption(f"Database detail: {error}")
        st.stop()

    return build_inventory_projection(
        inventory, usage_history, settings, include_inactive=include_inactive
    )


def reset_editor_state():
    st.session_state.pop("inventory_editor", None)


def archive_uploaded_report(uploaded_file, report_name):
    """Keep the source report that produced the current database snapshot."""
    ensure_data_directories()
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    destination = IMPORT_DIR / f"{timestamp}_{report_name}.csv"
    uploaded_file.seek(0)
    destination.write_bytes(uploaded_file.read())
    uploaded_file.seek(0)
    return destination


def item_key(row):
    return f"{row.sku}|{row.branch_id}"


def initialize_selection(projection):
    if "selected_item_keys" not in st.session_state:
        st.session_state.selected_item_keys = set()
    if "order_amount_overrides" not in st.session_state:
        st.session_state.order_amount_overrides = {}

    if not st.session_state.get("selection_initialized"):
        st.session_state.selected_item_keys = set()
        st.session_state.selection_initialized = True


def add_order_amounts(projection):
    display = projection.copy()
    display["order_amount"] = display["item_key"].map(
        st.session_state.order_amount_overrides
    )
    display["order_amount"] = display["order_amount"].fillna(
        display["recommended_order_qty"]
    ).fillna(0)
    return display


def update_order_state(edited_table, visible_keys):
    selected_visible = set(
        edited_table.loc[edited_table["order_selected"], "item_key"]
    )
    st.session_state.selected_item_keys.difference_update(visible_keys)
    st.session_state.selected_item_keys.update(selected_visible)

    for row in edited_table.itertuples(index=False):
        recommended = 0 if pd.isna(row.recommended_order_qty) else row.recommended_order_qty
        amount = 0 if pd.isna(row.order_amount) else row.order_amount
        if amount == recommended:
            st.session_state.order_amount_overrides.pop(row.item_key, None)
        else:
            st.session_state.order_amount_overrides[row.item_key] = amount


def build_order_export(selected_items, selected_branch_ids):
    branches = load_branches()
    selected_branches = {
        branch_id: branches[branch_id]
        for branch_id in selected_branch_ids
    }
    branch_columns = [
        f"branch {branch_id} ({name.lower()})"
        for branch_id, name in selected_branches.items()
    ]
    orders = selected_items.pivot_table(
        index=["sku", "description"],
        columns="branch_id",
        values="order_amount",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    orders = orders.rename(columns={
        branch_id: f"branch {branch_id} ({name.lower()})"
        for branch_id, name in selected_branches.items()
    })
    for column in branch_columns:
        if column not in orders:
            orders[column] = 0
    orders["total order (all branches)"] = orders[branch_columns].sum(axis=1)
    orders = orders.rename(columns={"sku": "item"})
    return orders[["item", "description", "total order (all branches)", *branch_columns]]


def main():
    st.title("ECI Spruce Inventory Reorder Tool")
    st.caption("Recommendations and selections are managed separately for each branch.")

    current_settings = load_settings()
    branches = load_branches()
    with st.sidebar:
        st.header("Reorder settings")
        with st.form("settings_form"):
            stock_target_days = st.number_input("Stock target (days)", min_value=0.0, value=float(current_settings["stock_target_days"]), step=1.0)
            vendor_lead_time_days = st.number_input("Vendor lead time (days)", min_value=0.0, value=float(current_settings["vendor_lead_time_days"]), step=1.0)
            buffer_days = st.number_input("Buffer time (days)", min_value=0.0, value=float(current_settings["buffer_days"]), step=1.0)
            save_clicked = st.form_submit_button("Save settings")

        if save_clicked:
            save_settings({
                "stock_target_days": stock_target_days,
                "vendor_lead_time_days": vendor_lead_time_days,
                "buffer_days": buffer_days,
            })
            reset_editor_state()
            st.success("Settings saved.")
            st.rerun()

        st.header("Import Spruce reports")
        st.caption("Upload both reports to replace the current database snapshot.")
        stock_file = st.file_uploader(
            "Stock Status CSV", type=["csv", "CSV"], key="stock_upload"
        )
        usage_file = st.file_uploader(
            "12-month Usage CSV", type=["csv", "CSV"], key="usage_upload"
        )
        import_clicked = st.button(
            "Process and save reports",
            disabled=stock_file is None or usage_file is None,
            use_container_width=True,
        )

        if import_clicked:
            try:
                imported_inventory = load_spruce_stock(stock_file)
                imported_usage = load_spruce_usage(usage_file)
                if imported_inventory.empty:
                    raise ValueError("The stock report did not contain any branch inventory rows.")
                if imported_usage.empty:
                    raise ValueError("The usage report did not contain any branch usage rows.")

                replace_imported_data(imported_inventory, imported_usage)
                archive_uploaded_report(stock_file, "stock")
                archive_uploaded_report(usage_file, "usage")
                st.session_state.pop("selection_initialized", None)
                st.session_state.pop("selected_item_keys", None)
                st.session_state.pop("order_amount_overrides", None)
                reset_editor_state()
                st.success(
                    f"Saved {len(imported_inventory):,} inventory rows and "
                    f"{len(imported_usage):,} usage rows."
                )
                st.rerun()
            except Exception as error:
                st.error(f"Import failed: {error}")

    include_inactive = False
    selected_branch_ids = list(branches)
    projection = load_projection(current_settings, include_inactive)
    projection["item_key"] = projection.apply(item_key, axis=1)
    initialize_selection(projection)

    st.subheader("Filters")
    filter_columns = st.columns([1.4, 1.4, 2.4, 1.2])
    with filter_columns[0]:
        selected_branch_ids = st.multiselect(
            "Branches to show and export",
            options=list(branches),
            default=list(branches),
            format_func=lambda branch_id: f"{branch_id} — {branches[branch_id]}",
        )

    with filter_columns[1]:
        vendor_filter = st.text_input("Vendor", placeholder="Vendor code")
    with filter_columns[2]:
        search_text = st.text_input("SKU or description", placeholder="Search items")
    with filter_columns[3]:
        include_inactive = st.checkbox("Show inactive", value=False)

    if include_inactive:
        projection = load_projection(current_settings, include_inactive)
        projection["item_key"] = projection.apply(item_key, axis=1)
    display = add_order_amounts(projection)
    display = display.loc[display["branch_id"].isin(selected_branch_ids)]
    if search_text:
        matches = (
            display["sku"].str.contains(search_text, case=False, na=False)
            | display["description"].str.contains(search_text, case=False, na=False)
            | display["vendor"].str.contains(search_text, case=False, na=False)
            | display["branch_name"].str.contains(search_text, case=False, na=False)
            | display["branch_id"].str.contains(search_text, case=False, na=False)
        )
        display = display.loc[matches]
    if vendor_filter:
        display = display.loc[
            display["vendor"].astype("string").str.contains(
                vendor_filter, case=False, na=False
            )
        ]
    display["order_selected"] = display["item_key"].isin(st.session_state.selected_item_keys)

    select_column, clear_column, summary_column = st.columns([1, 1, 3])
    with select_column:
        if st.button("Select visible recommended"):
            st.session_state.selected_item_keys.update(
                display.loc[display["recommended_order_qty"].gt(0), "item_key"]
            )
            reset_editor_state()
            st.rerun()
    with clear_column:
        if st.button("Clear selection"):
            st.session_state.selected_item_keys.clear()
            reset_editor_state()
            st.rerun()
    with summary_column:
        st.caption("Use the Order? checkbox and Order amount for each SKU/branch.")

    edited = st.data_editor(
        display,
        key="inventory_editor",
        hide_index=True,
        width="stretch",
        height=600,
        disabled=[column for column in display if column not in {"order_selected", "order_amount"}],
        column_order=[
            "order_selected", "sku", "description", "vendor", "branch_id", "branch_name",
            "on_hand", "on_order", "available", "last_12_month_sales", "avg_daily_sales",
            "projected_days_remaining", "recommended_order_qty", "order_amount",
        ],
        column_config={
            "order_selected": st.column_config.CheckboxColumn("Order?"),
            "branch_id": st.column_config.TextColumn("Branch"),
            "branch_name": st.column_config.TextColumn("Branch name"),
            "on_hand": st.column_config.NumberColumn("On hand", format="%.0f"),
            "on_order": st.column_config.NumberColumn("On order", format="%.0f"),
            "last_12_month_sales": st.column_config.NumberColumn("12-month sales", format="%.0f"),
            "avg_daily_sales": st.column_config.NumberColumn("Avg. daily sales", format="%.3f"),
            "projected_days_remaining": st.column_config.NumberColumn("Projected days", format="%.1f"),
            "recommended_order_qty": st.column_config.NumberColumn("Recommended order", format="%.0f"),
            "order_amount": st.column_config.NumberColumn("Order amount", min_value=0, step=1, format="%.0f"),
        },
    )
    update_order_state(edited, set(display["item_key"]))

    selected = add_order_amounts(projection).loc[
        projection["item_key"].isin(st.session_state.selected_item_keys)
    ].copy()
    selected = selected.loc[selected["branch_id"].isin(selected_branch_ids)]
    selected = selected.loc[selected["order_amount"].gt(0)]
    item_metric, unit_metric = st.columns(2)
    item_metric.metric("Selected SKU/branch orders", len(selected))
    unit_metric.metric("Total units", f"{selected['order_amount'].sum():,.0f}")

    if not selected.empty:
        order_export = build_order_export(selected, selected_branch_ids)
        st.subheader("Purchase-order preview")
        st.dataframe(order_export, hide_index=True, width="stretch")
        st.download_button(
            "Download consolidated order CSV",
            order_export.to_csv(index=False).encode("utf-8"),
            file_name="purchase_order_draft.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
