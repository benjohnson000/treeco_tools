import numpy as np
import pandas as pd


DAYS_PER_YEAR = 365.25


def build_inventory_projection(inventory, usage_history, settings, include_inactive=False):
    """Calculate reorder quantities separately for each SKU and branch."""
    inventory = inventory.copy()
    usage_history = usage_history.copy()
    inventory["branch_id"] = inventory["branch_id"].astype(str)
    usage_history["branch_id"] = usage_history["branch_id"].astype(str)

    remap_sources = []
    if settings.get("location_remap_enabled"):
        remap_sources = [str(source) for source in settings["location_remap_sources"]]
        remap_target = str(settings["location_remap_target"])
        usage_history["branch_id"] = usage_history["branch_id"].replace(
            dict.fromkeys(remap_sources, remap_target)
        )
        usage_history = usage_history.groupby(
            ["sku", "branch_id"], as_index=False, dropna=False
        )["last_12_month_sales"].sum()

    projection = inventory.merge(
        usage_history, on=["sku", "branch_id"], how="left"
    )
    projection["last_12_month_sales"] = projection["last_12_month_sales"].fillna(0)
    projection["avg_daily_sales"] = (
        projection["last_12_month_sales"] / DAYS_PER_YEAR
    )
    # Incoming purchase orders are part of the inventory position: they should
    # extend coverage and reduce any new recommendation.
    projection["inventory_position"] = (
        projection["available"].fillna(0) + projection["on_order"].fillna(0)
    )

    if not include_inactive:
        projection = projection.loc[
        ~(projection["on_hand"].eq(0) & projection["last_12_month_sales"].eq(0))
        ].copy()

    projection["projected_days_remaining"] = (
        projection["inventory_position"] / projection["avg_daily_sales"]
    )
    projection.loc[projection["avg_daily_sales"].le(0), "projected_days_remaining"] = pd.NA

    target_coverage_days = (
        settings["stock_target_days"]
        + settings["vendor_lead_time_days"]
    )
    projection["recommended_order_qty"] = np.ceil(
        (
            projection["avg_daily_sales"] * target_coverage_days
            - projection["inventory_position"]
        )
        .clip(lower=0)
    )
    projection.loc[projection["avg_daily_sales"].le(0), "recommended_order_qty"] = 0

    if remap_sources:
        projection = projection.loc[~projection["branch_id"].isin(remap_sources)].copy()

    output_columns = [
        "sku", "description", "vendor", "branch_id", "branch_name", "on_hand",
        "on_order", "available", "last_12_month_sales", "avg_daily_sales",
        "projected_days_remaining", "recommended_order_qty",
    ]
    return projection[output_columns].round({
        "last_12_month_sales": 1,
        "avg_daily_sales": 3,
        "projected_days_remaining": 1,
        "recommended_order_qty": 0,
    })
