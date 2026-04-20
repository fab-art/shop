import pandas as pd
import streamlit as st

from app.core import require_supabase, init_session_state, log_audit, require_admin, safe_float
from app.ui import inject_design_system

st.set_page_config(page_title="Finance", page_icon="📊", layout="wide")
inject_design_system()
init_session_state()
require_admin()
sb = require_supabase()

st.title("📊 Finance")

orders = sb.table("sales_orders").select("total_amount").execute().data or []
lines = sb.table("order_lines").select("line_cogs").execute().data or []
expenses = sb.table("expenses").select("amount").execute().data or []
invoices = sb.table("purchase_invoices").select("landed_cost,status,supplier_id").execute().data or []
suppliers = {s["supplier_id"]: s["name"] for s in (sb.table("suppliers").select("supplier_id,name").execute().data or [])}

revenue = sum(safe_float(x.get("total_amount")) for x in orders)
cogs = sum(safe_float(x.get("line_cogs")) for x in lines)
exp_total = sum(safe_float(x.get("amount")) for x in expenses)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", f"{revenue:,.2f}")
c2.metric("COGS", f"{cogs:,.2f}")
c3.metric("Gross Profit", f"{revenue-cogs:,.2f}")
c4.metric("Expenses", f"{exp_total:,.2f}")
c5.metric("Net Profit", f"{revenue-cogs-exp_total:,.2f}")

st.subheader("Accounts Payable")
ap = {}
for inv in invoices:
    if inv.get("status") == "On Credit":
        sname = suppliers.get(inv.get("supplier_id"), "Unknown")
        ap[sname] = ap.get(sname, 0) + safe_float(inv.get("landed_cost"))

if ap:
    st.dataframe(pd.DataFrame(ap.items(), columns=["Supplier", "Payable"]), use_container_width=True)
else:
    st.info("No outstanding payables")

st.subheader("Log Expense")
with st.form("expense_form"):
    d1, d2, d3 = st.columns(3)
    description = d1.text_input("Description")
    amount = d2.number_input("Amount", min_value=0.0, value=0.0, step=1.0)
    category = d3.selectbox("Category", ["Rent", "Transport", "Utilities", "Salaries", "Supplies", "Other"])
    submit = st.form_submit_button("Save Expense")
    if submit:
        if not description.strip() or amount < 0:
            st.error("Valid description and amount required")
        else:
            exp = sb.table("expenses").insert(
                {"description": description.strip(), "amount": amount, "category": category}
            ).execute().data[0]
            log_audit(sb, "UPDATE", "expenses", exp["expense_id"], {}, exp)
            st.success("Expense saved")
            st.rerun()
