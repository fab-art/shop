import pandas as pd
import streamlit as st

from app.core import require_supabase, init_session_state, log_audit, require_auth
from app.ui import inject_design_system

st.set_page_config(page_title="Orders", page_icon="📋", layout="wide")
inject_design_system()
init_session_state()
require_auth()
sb = require_supabase()

st.title("📋 Orders")

orders = sb.table("sales_orders").select("*").order("created_at", desc=True).limit(200).execute().data or []
lines = sb.table("order_lines").select("*").order("created_at", desc=True).limit(500).execute().data or []

st.dataframe(pd.DataFrame(orders), use_container_width=True)

st.subheader("Order Lines (View-only)")
st.dataframe(pd.DataFrame(lines), use_container_width=True)

if st.session_state["role"] == "admin" and orders:
    st.subheader("Admin: Update Order Status")
    with st.form("order_status_form"):
        order_map = {f"{o['order_id'][:8]} · {o['customer_name']}": o for o in orders}
        pick = st.selectbox("Order", list(order_map.keys()))
        order = order_map[pick]
        old_status = order.get("status", "Pending")
        new_status = st.selectbox("Status", ["Pending", "Completed", "Cancelled"])
        submit = st.form_submit_button("Save")
        if submit:
            allowed = {
                "Pending": {"Pending", "Completed", "Cancelled"},
                "Completed": {"Completed"},
                "Cancelled": {"Cancelled"},
            }
            if new_status not in allowed.get(old_status, {old_status}):
                st.error("Invalid status transition")
                st.stop()

            updated = sb.table("sales_orders").update({"status": new_status}).eq("order_id", order["order_id"]).execute().data[0]
            log_audit(sb, "UPDATE", "sales_orders", order["order_id"], order, updated)

            if old_status != "Cancelled" and new_status == "Cancelled":
                order_lines = sb.table("order_lines").select("*").eq("order_id", order["order_id"]).execute().data or []
                for line in order_lines:
                    sb.table("inventory_ledger").insert(
                        {
                            "item_id": line["item_id"],
                            "transaction_type": "ADJUSTMENT",
                            "quantity_change": float(line["quantity"]),
                            "unit_cost": 0,
                            "reason": f"Order {order['order_id']} cancelled",
                        }
                    ).execute()

            st.success("Order updated")
            st.rerun()
