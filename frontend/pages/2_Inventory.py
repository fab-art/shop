import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils import get_sb, load_inventory

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")
sb = get_sb()

st.title("📦 Inventory & Inwarding")

inv = load_inventory(sb)
df = pd.DataFrame(inv) if inv else pd.DataFrame()

if not df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", len(df))
    low = df[df["stock_on_hand"] < 5]
    col2.metric("Low Stock", len(low), delta=f"-{len(low)}" if len(low) else None, delta_color="inverse")
    col3.metric("Inventory Value", f"{(df['stock_on_hand'] * df['current_landed_cost']).sum():,.2f}")
    st.divider()
    search = st.text_input("🔍 Search")
    display = df if not search else df[df["name"].str.contains(search, case=False)]
    st.dataframe(display[["name","type","uom","stock_on_hand","current_landed_cost","default_sell_price"]], use_container_width=True, hide_index=True)
else:
    st.info("No inventory yet.")

st.divider()
st.subheader("📥 Receive Stock")

suppliers = sb.table("suppliers").select("supplier_id,name").execute().data
supplier_map = {s["name"]: s["supplier_id"] for s in suppliers}

with st.expander("➕ Add New Supplier"):
    ns = st.text_input("Supplier Name")
    np_ = st.text_input("Phone")
    if st.button("Save Supplier"):
        sb.table("suppliers").insert({"name": ns, "phone": np_}).execute()
        st.success("Saved!")
        st.rerun()

mode = st.radio("Item", ["Existing Item", "New Item"], horizontal=True)
if mode == "Existing Item" and not df.empty:
    label = st.selectbox("Select Item", df["name"].tolist())
    item_id = df[df["name"] == label]["item_id"].values[0]
    item_name = item_type = item_uom = None
else:
    item_id = None
    item_name = st.text_input("Item Name")
    item_type = st.selectbox("Type", ["Material", "Product", "Service"])
    item_uom = st.selectbox("UOM", ["Meters", "Pieces", "Flat Rate"])

c1, c2 = st.columns(2)
with c1:
    qty = st.number_input("Quantity", min_value=0.01, value=1.0, step=0.5)
    purchase_price = st.number_input("Total Purchase Price", min_value=0.0, value=0.0)
with c2:
    freight = st.number_input("Freight Cost", min_value=0.0, value=0.0)
    pay_status = st.selectbox("Payment", ["On Credit", "Paid"])
    sup_name = st.selectbox("Supplier", list(supplier_map.keys()) if supplier_map else ["—"])

lc = (purchase_price + freight) / qty if qty else 0
st.info(f"Landed Cost per unit: **{lc:,.2f}**")

if st.button("✅ Receive Stock", type="primary"):
    with st.spinner("Saving..."):
        landed_cost_per_unit = lc

        if not item_id:
            res = sb.table("catalog").insert({
                "name": item_name,
                "type": item_type,
                "uom": item_uom,
                "current_landed_cost": round(landed_cost_per_unit, 2),
                "default_sell_price": round(landed_cost_per_unit * 1.3, 2)
            }).execute()
            item_id = res.data[0]["item_id"]
        else:
            cat = sb.table("catalog").select("current_landed_cost").eq("item_id", item_id).execute()
            ledger = sb.table("inventory_ledger").select("quantity_change").eq("item_id", item_id).execute()
            old_cost = cat.data[0]["current_landed_cost"] if cat.data else 0
            old_qty = max(sum(r["quantity_change"] for r in ledger.data) if ledger.data else 0, 0)
            new_avg = ((old_qty * old_cost) + (qty * landed_cost_per_unit)) / (old_qty + qty)
            sb.table("catalog").update({"current_landed_cost": round(new_avg, 2)}).eq("item_id", item_id).execute()

        sb.table("inventory_ledger").insert({
            "item_id": item_id,
            "transaction_type": "INWARD",
            "quantity_change": qty,
            "unit_cost": round(landed_cost_per_unit, 2)
        }).execute()

        invoice = {
            "item_id": item_id,
            "quantity": qty,
            "purchase_price": purchase_price,
            "freight_cost": freight,
            "status": pay_status
        }
        if supplier_map.get(sup_name):
            invoice["supplier_id"] = supplier_map[sup_name]
        sb.table("purchase_invoices").insert(invoice).execute()

        st.success("Stock received!")
        st.rerun()
