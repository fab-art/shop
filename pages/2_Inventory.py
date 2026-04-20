import pandas as pd
import streamlit as st

from app.core import require_supabase, init_session_state, log_audit, require_auth, safe_float
from app.ui import inject_design_system

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")
inject_design_system()
init_session_state()
require_auth()
sb = require_supabase()

st.title("📦 Inventory")

catalog = sb.table("catalog").select("*").order("name").execute().data or []
ledger = sb.table("inventory_ledger").select("item_id,quantity_change").execute().data or []

totals = {}
for r in ledger:
    totals[r["item_id"]] = totals.get(r["item_id"], 0) + safe_float(r["quantity_change"])

for c in catalog:
    c["stock_on_hand"] = totals.get(c["item_id"], 0)

inv_df = pd.DataFrame(catalog)
if not inv_df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Items", len(inv_df))
    low = inv_df[inv_df["stock_on_hand"] < 5]
    c2.metric("Low Stock", len(low))
    c3.metric("Inventory Value", f"{(inv_df['stock_on_hand'] * inv_df['current_landed_cost']).sum():,.2f}")
    st.dataframe(inv_df[["name", "type", "uom", "stock_on_hand", "current_landed_cost", "default_sell_price"]], use_container_width=True)

st.divider()
st.subheader("Stock Inward")
with st.form("inward_form"):
    mode = st.radio("Item Mode", ["Existing", "New"], horizontal=True)
    if mode == "Existing" and catalog:
        mapper = {f"{x['name']} ({x['item_id'][:8]})": x for x in catalog}
        label = st.selectbox("Item", list(mapper.keys()))
        selected = mapper[label]
        item_id = selected["item_id"]
        name = selected["name"]
        item_type = selected["type"]
        uom = selected["uom"]
    else:
        name = st.text_input("Name")
        item_type = st.selectbox("Type", ["Material", "Product", "Service"])
        uom = st.selectbox("UOM", ["Meters", "Pieces", "Unit"])
        item_id = None

    qty = st.number_input("Quantity", min_value=0.01, value=1.0, step=0.5)
    purchase_price = st.number_input("Purchase Price", min_value=0.0, value=0.0, step=0.01)
    freight = st.number_input("Freight", min_value=0.0, value=0.0, step=0.01)
    status = st.selectbox("Invoice Status", ["On Credit", "Paid"])
    submit = st.form_submit_button("Receive Stock")

    if submit:
        landed = (purchase_price + freight) / qty
        if not item_id:
            created = sb.table("catalog").insert(
                {
                    "name": name,
                    "type": item_type,
                    "uom": uom,
                    "current_landed_cost": round(landed, 2),
                    "default_sell_price": round(landed * 1.3, 2),
                }
            ).execute().data[0]
            item_id = created["item_id"]
        else:
            existing_cost = next((safe_float(c["current_landed_cost"]) for c in catalog if c["item_id"] == item_id), 0)
            existing_qty = max(totals.get(item_id, 0), 0)
            new_avg = ((existing_qty * existing_cost) + (qty * landed)) / (existing_qty + qty)
            sb.table("catalog").update({"current_landed_cost": round(new_avg, 2)}).eq("item_id", item_id).execute()

        sb.table("inventory_ledger").insert(
            {
                "item_id": item_id,
                "transaction_type": "INWARD",
                "quantity_change": qty,
                "unit_cost": round(landed, 2),
                "reason": "Stock inward",
            }
        ).execute()

        sb.table("purchase_invoices").insert(
            {
                "item_id": item_id,
                "quantity": qty,
                "purchase_price": purchase_price,
                "freight_cost": freight,
                "landed_cost": round(landed, 2),
                "status": status,
            }
        ).execute()
        st.success("Stock received")
        st.rerun()

st.divider()
st.subheader("Admin Inventory Adjustment")
if st.session_state["role"] != "admin":
    st.info("Admin only")
else:
    with st.form("adjust_form"):
        mapper = {f"{x['name']} ({x['item_id'][:8]})": x for x in catalog}
        item_label = st.selectbox("Item", list(mapper.keys()))
        adj_qty = st.number_input("Quantity change (+/-)", value=0.0, step=0.5)
        reason = st.text_input("Reason")
        adj_submit = st.form_submit_button("Post Adjustment")
        if adj_submit:
            if adj_qty == 0 or not reason.strip():
                st.error("Quantity and reason are required")
            else:
                item = mapper[item_label]
                tx = sb.table("inventory_ledger").insert(
                    {
                        "item_id": item["item_id"],
                        "transaction_type": "ADJUSTMENT",
                        "quantity_change": adj_qty,
                        "unit_cost": safe_float(item.get("current_landed_cost")),
                        "reason": reason.strip(),
                    }
                ).execute().data[0]
                log_audit(sb, "UPDATE", "inventory_ledger", tx["ledger_id"], {}, tx)
                st.success("Adjustment saved")
                st.rerun()
