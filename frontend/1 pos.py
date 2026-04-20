import streamlit as st
import os
from supabase import create_client

@st.cache_resource
def get_sb():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

st.set_page_config(page_title="POS", page_icon="🛒", layout="wide")
sb = get_sb()
st.title("🛒 Point of Sale")

catalog = sb.table("catalog").select("item_id,name,uom,default_sell_price").execute().data
catalog_map = {f"{c['name']} ({c['uom']})": c for c in catalog}

if "cart" not in st.session_state:
    st.session_state.cart = []

col1, col2 = st.columns(2)

with col1:
    st.subheader("Add Item")
    if catalog_map:
        label = st.selectbox("Product / Material", list(catalog_map.keys()))
        item = catalog_map[label]
        qty = st.number_input("Quantity", min_value=0.01, value=1.0, step=0.5)
        price = st.number_input("Unit Price", min_value=0.0, value=float(item["default_sell_price"]))
        if st.button("➕ Add to Cart"):
            st.session_state.cart.append({
                "item_id": item["item_id"], "name": item["name"],
                "uom": item["uom"], "quantity": qty, "unit_price": price
            })
            st.rerun()
    else:
        st.info("No items in catalog. Add stock from Inventory page first.")

with col2:
    st.subheader("Cart")
    if not st.session_state.cart:
        st.write("Cart is empty.")
    else:
        for i, line in enumerate(st.session_state.cart):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{line['name']}** — {line['quantity']} {line['uom']} × {line['unit_price']}")
            if c2.button("❌", key=f"rm_{i}"):
                st.session_state.cart.pop(i)
                st.rerun()

        total = sum(l["quantity"] * l["unit_price"] for l in st.session_state.cart)
        st.markdown(f"### Total: **{total:,.2f}**")
        st.divider()
        cname = st.text_input("Customer Name")
        cphone = st.text_input("Customer Phone")
        deposit = st.number_input("Upfront Deposit", min_value=0.0, value=0.0)

        if st.button("✅ Submit Order", type="primary"):
            if not cname:
                st.error("Customer name required.")
            else:
                with st.spinner("Submitting order..."):
                    item_ids = [l["item_id"] for l in st.session_state.cart]
                    cat_res = sb.table("catalog").select("item_id,current_landed_cost").in_("item_id", item_ids).execute()
                    cost_map = {r["item_id"]: r["current_landed_cost"] for r in cat_res.data}

                    order = sb.table("sales_orders").insert({
                        "customer_name": cname, "customer_phone": cphone,
                        "total_amount": total, "deposit_paid": deposit, "status": "Pending"
                    }).execute()
                    order_id = order.data[0]["order_id"]

                    for line in st.session_state.cart:
                        cogs = cost_map.get(line["item_id"], 0) * line["quantity"]
                        sb.table("order_lines").insert({
                            "order_id": order_id, "item_id": line["item_id"],
                            "quantity": line["quantity"], "unit_price": line["unit_price"], "line_cogs": cogs
                        }).execute()
                        sb.table("inventory_ledger").insert({
                            "item_id": line["item_id"], "transaction_type": "SALE",
                            "quantity_change": -line["quantity"], "unit_cost": cost_map.get(line["item_id"], 0)
                        }).execute()

                    st.success(f"Order placed! ID: `{order_id}`")
                    st.info(f"Balance Due: **{total - deposit:,.2f}**")
                    st.session_state.cart = []
