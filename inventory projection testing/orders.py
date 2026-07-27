"""Build the consolidated purchase-order export."""

from branches import load_branches


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
