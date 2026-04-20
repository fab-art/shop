import streamlit as st

from app.core import require_supabase, init_session_state, require_auth, safe_float
from app.core import get_supabase, init_session_state, require_auth, safe_float
from app.ui import inject_design_system

st.set_page_config(page_title="POS", page_icon="🛒", layout="wide")
inject_design_system()
init_session_state()
require_auth()
sb = require_supabase()
sb = get_supabase()

st.title("🛒 Point of Sale")

catalog = sb.table("catalog").select("item_id,name,uom,default_sell_price,current_landed_cost").order("name").execute().data or []
catalog_map = {f"{c['name']} ({c['uom']})": c for c in catalog}

c1, c2 = st.columns(2)
with c1:
    st.subheader("Add Item")
    if catalog_map:
        selected = st.selectbox("Product", list(catalog_map.keys()))
        item = catalog_map[selected]
        qty = st.number_input("Quantity", min_value=0.01, value=1.0, step=0.5)
        unit_price = st.number_input("Unit Price", min_value=0.0, value=safe_float(item.get("default_sell_price")), step=0.01)
        if st.button("Add to Cart"):
            st.session_state["cart"].append(
                {
                    "item_id": item["item_id"],
                    "name": item["name"],
                    "uom": item["uom"],
                    "quantity": qty,
                    "unit_price": unit_price,
                    "cost": safe_float(item.get("current_landed_cost")),
                }
            )
            st.rerun()
    else:
        st.warning("No catalog items available.")

with c2:
    st.subheader("Cart")
    if not st.session_state["cart"]:
        st.info("Cart is empty")
    else:
        for i, row in enumerate(st.session_state["cart"]):
            rc1, rc2 = st.columns([6, 1])
            rc1.write(f"{row['name']} · {row['quantity']} {row['uom']} × {row['unit_price']:.2f}")
            if rc2.button("✕", key=f"rm_{i}"):
                st.session_state["cart"].pop(i)
                st.rerun()

        total = sum(r["quantity"] * r["unit_price"] for r in st.session_state["cart"])
        st.metric("Total", f"{total:,.2f}")
        with st.form("checkout_form"):
            customer_name = st.text_input("Customer Name*")
            customer_phone = st.text_input("Customer Phone")
            deposit = st.number_input("Deposit", min_value=0.0, value=0.0, step=1.0)
            submit = st.form_submit_button("Checkout")
            if submit:
                if not customer_name.strip():
                    st.error("Customer name is required")
                    st.stop()

                order = sb.table("sales_orders").insert(
                    {
                        "customer_name": customer_name.strip(),
                        "customer_phone": customer_phone.strip(),
                        "total_amount": total,
                        "deposit_paid": deposit,
                        "balance_due": total - deposit,
                        "status": "Pending",
                    }
                ).execute().data[0]

                for line in st.session_state["cart"]:
                    line_total = line["quantity"] * line["unit_price"]
                    sb.table("order_lines").insert(
                        {
                            "order_id": order["order_id"],
                            "item_id": line["item_id"],
                            "quantity": line["quantity"],
                            "unit_price": line["unit_price"],
                            "line_total": line_total,
                            "line_cogs": line["quantity"] * line["cost"],
                        }
                    ).execute()
                    sb.table("inventory_ledger").insert(
                        {
                            "item_id": line["item_id"],
                            "transaction_type": "SALE",
                            "quantity_change": -line["quantity"],
                            "unit_cost": line["cost"],
                            "reason": f"Sale {order['order_id']}",
                        }
                    ).execute()

                st.session_state["cart"] = []
                st.success(f"Order created: {order['order_id']}")
                st.rerun()
