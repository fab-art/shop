import streamlit as st
import requests
import os
from supabase import create_client

st.set_page_config(page_title="POS", page_icon="🛒", layout="wide")

@st.cache_resource
def get_sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

API_URL = os.environ.get("API_URL", "http://localhost:8000")

sb = get_sb()

st.title("🛒 Point of Sale")

# Load catalog
catalog = sb.table("catalog").select("item_id,name,uom,default_sell_price").execute().data
catalog_map = {f"{c['name']} ({c['uom']})": c for c in catalog}

# Cart in session state
if "cart" not in st.session_state:
    st.session_state.cart = []

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Add Item")
    if catalog_map:
        selected_label = st.selectbox("Product / Material", list(catalog_map.keys()))
        item = catalog_map[selected_label]
        qty = st.number_input("Quantity", min_value=0.01, value=1.0, step=0.5)
        price = st.number_input("Unit Price", min_value=0.0, value=float(item["default_sell_price"]))
        if st.button("➕ Add to Cart"):
            st.session_state.cart.append({
                "item_id": item["item_id"],
                "name": item["name"],
                "uom": item["uom"],
                "quantity": qty,
                "unit_price": price
            })
            st.rerun()
    else:
        st.info("No items in catalog yet. Add stock from Inventory page.")

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
                payload = {
                    "customer_name": cname,
                    "customer_phone": cphone,
                    "deposit_paid": deposit,
                    "lines": [
                        {"item_id": l["item_id"], "quantity": l["quantity"], "unit_price": l["unit_price"]}
                        for l in st.session_state.cart
                    ]
                }
                with st.spinner("Processing order... (first run may take ~30s while server wakes up)"):
                    try:
                        r = requests.post(f"{API_URL}/api/orders/checkout", json=payload, timeout=90)
                        r.raise_for_status()
                        result = r.json()
                        st.success(f"Order placed! ID: `{result['order_id']}`")
                        st.info(f"Balance Due: **{result['balance_due']:,.2f}**")
                        st.markdown(f"📱 Track link: `{API_URL}/track/{result['order_id']}`")
                        st.session_state.cart = []
                    except Exception as e:
                        st.error(f"Error: {e}")
