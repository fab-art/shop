import streamlit as st
import pandas as pd
from supabase import create_client

@st.cache_resource
def get_sb():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

st.set_page_config(page_title="Finance", page_icon="📊", layout="wide")
sb = get_sb()
st.title("📊 Financial Dashboard")

orders = sb.table("sales_orders").select("total_amount").execute().data
lines = sb.table("order_lines").select("line_cogs").execute().data
expenses = sb.table("expenses").select("amount").execute().data

revenue = sum(o["total_amount"] for o in orders)
cogs = sum(l["line_cogs"] for l in lines)
total_exp = sum(e["amount"] for e in expenses)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"{revenue:,.2f}")
c2.metric("COGS", f"{cogs:,.2f}")
c3.metric("Gross Profit", f"{revenue - cogs:,.2f}")
c4.metric("Net Profit", f"{revenue - cogs - total_exp:,.2f}")

st.divider()
st.subheader("Supplier Accounts Payable")
invoices = sb.table("purchase_invoices").select("landed_cost,suppliers(name)").eq("status", "On Credit").execute().data
if invoices:
    ap = {}
    for inv in invoices:
        name = inv["suppliers"]["name"] if inv.get("suppliers") else "Unknown"
        ap[name] = ap.get(name, 0) + (inv["landed_cost"] or 0)
    st.dataframe(pd.DataFrame(ap.items(), columns=["Supplier", "Owed"]), use_container_width=True, hide_index=True)
    st.metric("Total Payable", f"{sum(ap.values()):,.2f}")
else:
    st.success("No outstanding payables.")

st.divider()
st.subheader("Log Expense")
c1, c2, c3 = st.columns(3)
with c1: desc = st.text_input("Description")
with c2: amount = st.number_input("Amount", min_value=0.0)
with c3: cat = st.selectbox("Category", ["Electricity", "Transport", "Rent", "Salaries", "Supplies", "Other"])
if st.button("Log Expense"):
    if desc and amount > 0:
        sb.table("expenses").insert({"description": desc, "amount": amount, "category": cat}).execute()
        st.success("Logged!")
        st.rerun()

st.divider()
st.subheader("Recent Expenses")
exp = sb.table("expenses").select("*").order("expense_date", desc=True).limit(30).execute().data
if exp:
    st.dataframe(pd.DataFrame(exp)[["expense_date","category","description","amount"]], use_container_width=True, hide_index=True)

st.divider()
st.subheader("Recent Orders")
ords = sb.table("sales_orders").select("*").order("created_at", desc=True).limit(20).execute().data
if ords:
    st.dataframe(pd.DataFrame(ords)[["created_at","customer_name","status","total_amount","deposit_paid","balance_due"]], use_container_width=True, hide_index=True)
