import streamlit as st
import requests
import os
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")

@st.cache_resource
def get_sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

API_URL = os.environ.get("API_URL", "http://localhost:8000")
sb = get_sb()

st.title("📦 Inventory & Inwarding")

# Build inventory from catalog + ledger (view not exposed via Supabase REST API)
def load_inventory():
    catalog_rows = sb.table("catalog").select("item_id,name,type,uom,current_landed_cost,default_sell_price").execute().data
    ledger_rows = sb.table("inventory_ledger").select("item_id,quantity_change").execute().data
    totals = {}
    for r in ledger_rows:
        totals[r["item_id"]] = totals.get(r["item_id"], 0) + r["quantity_change"]
    for c in catalog_rows:
        c["stock_on_hand"] = round(totals.get(c["item_id"], 0), 3)
    return catalog_rows

inv = load_inventory()
df = pd.DataFrame(inv) if inv else pd.DataFrame()

if not df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", len(df))
    low = df[df["stock_on_hand"] < 5]
    col2.metric("Low Stock Warnings", len(low), delta=f"-{len(low)}" if len(low) else None, delta_color="inverse")
    total_val = (df["stock_on_hand"] * df["current_landed_cost"]).sum()
    col3.metric("Inventory Value", f"{total_val:,.2f}")
    st.divider()
    search = st.text_input("🔍 Search items")
    display = df if not search else df[df["name"].str.contains(search, case=False)]
    st.dataframe(display[["name","type","uom","stock_on_hand","current_landed_cost","default_sell_price"]], use_container_width=True, hide_index=True)
else:
    st.info("No inventory yet.")

st.divider()
st.subheader("📥 Receive Stock")

suppliers = sb.table("suppliers").select("supplier_id,name").execute().data
supplier_map = {s["name"]: s["supplier_id"] for s in suppliers}

with st.expander("➕ Add New Supplier"):
    new_sup = st.text_input("Supplier Name")
    new_sup_phone = st.text_input("Phone")
    if st.button("Save Supplier"):
        sb.table("suppliers").insert({"name": new_sup, "phone": new_sup_phone}).execute()
        st.success("Supplier added!")
        st.rerun()

mode = st.radio("Item", ["Existing Item", "New Item"], horizontal=True)

if mode == "Existing Item" and not df.empty:
    item_label = st.selectbox("Select Item", df["name"].tolist())
    item_id = df[df["name"] == item_label]["item_id"].values[0]
    item_name = item_type = item_uom = None
else:
    item_id = None
    item_name = st.text_input("Item Name")
    item_type = st.selectbox("Type", ["Material", "Product", "Service"])
    item_uom = st.selectbox("Unit of Measure", ["Meters", "Pieces", "Flat Rate"])

col1, col2 = st.columns(2)
with col1:
    qty = st.number_input("Quantity Received", min_value=0.01, value=1.0, step=0.5)
    purchase_price = st.number_input("Total Purchase Price", min_value=0.0, value=0.0)
with col2:
    freight = st.number_input("Freight / Transport Cost", min_value=0.0, value=0.0)
    pay_status = st.selectbox("Payment Status", ["On Credit", "Paid"])
    supplier_name = st.selectbox("Supplier", list(supplier_map.keys()) if supplier_map else ["—"])

lc = (purchase_price + freight) / qty if qty > 0 else 0
st.info(f"Landed Cost per unit: **{lc:,.2f}**")

if st.button("✅ Receive Stock", type="primary"):
    payload = {
        "item_id": item_id,
        "item_name": item_name,
        "item_type": item_type or "Material",
        "item_uom": item_uom or "Pieces",
        "supplier_id": supplier_map.get(supplier_name),
        "quantity": qty,
        "purchase_price": purchase_price,
        "freight_cost": freight,
        "status": pay_status
    }
    with st.spinner("Saving... (may take ~30s on cold start)"):
        try:
            r = requests.post(f"{API_URL}/api/inventory/inward", json=payload, timeout=90)
            r.raise_for_status()
            st.success("Stock received and landed cost updated!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
