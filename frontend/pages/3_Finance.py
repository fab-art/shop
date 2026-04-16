import streamlit as st
import os
import pandas as pd
import requests
from supabase import create_client

st.set_page_config(page_title="Finance", page_icon="📊", layout="wide")

@st.cache_resource
def get_sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

API_URL = os.environ.get("API_URL", "http://localhost:8000")
sb = get_sb()

st.title("📊 Financial Dashboard")

# --- P&L ---
st.subheader("Profit & Loss")
orders = sb.table("sales_orders").select("total_amount").execute().data
lines = sb.table("order_lines").select("line_cogs").execute().data
expenses = sb.table("expenses").select("amount").execute().data

revenue = sum(o["total_amount"] for o in orders)
cogs = sum(l["line_cogs"] for l in lines)
gross_profit = revenue - cogs
total_expenses = sum(e["amount"] for e in expenses)
net_profit = gross_profit - total_expenses

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gross Revenue", f"{revenue:,.2f}")
col2.metric("COGS", f"{cogs:,.2f}")
col3.metric("Gross Profit", f"{gross_profit:,.2f}")
col4.metric("Net Profit (after expenses)", f"{net_profit:,.2f}")

st.divider()

# --- Accounts Payable ---
st.subheader("Supplier Accounts Payable")
invoices = sb.table("purchase_invoices").select("status,landed_cost,suppliers(name)").eq("status", "On Credit").execute().data

if invoices:
    ap = {}
    for inv in invoices:
        name = inv["suppliers"]["name"] if inv.get("suppliers") else "Unknown"
        ap[name] = ap.get(name, 0) + inv["landed_cost"]
    ap_df = pd.DataFrame(ap.items(), columns=["Supplier", "Amount Owed"])
    st.dataframe(ap_df, use_container_width=True, hide_index=True)
    st.metric("Total Payable", f"{sum(ap.values()):,.2f}")
else:
    st.success("No outstanding payables.")

st.divider()

# --- Expense Logger ---
st.subheader("Log Expense")
col1, col2, col3 = st.columns(3)
with col1:
    desc = st.text_input("Description")
with col2:
    amount = st.number_input("Amount", min_value=0.0)
with col3:
    cat = st.selectbox("Category", ["Electricity", "Transport", "Rent", "Salaries", "Supplies", "Other"])

if st.button("Log Expense"):
    if desc and amount > 0:
        r = requests.post(f"{API_URL}/api/expenses", json={"description": desc, "amount": amount, "category": cat}, timeout=90)
        if r.ok:
            st.success("Logged!")
            st.rerun()
    else:
        st.error("Fill in description and amount.")

st.divider()
st.subheader("Recent Expenses")
exp_data = sb.table("expenses").select("*").order("expense_date", desc=True).limit(30).execute().data
if exp_data:
    st.dataframe(pd.DataFrame(exp_data)[["expense_date", "category", "description", "amount"]], use_container_width=True, hide_index=True)

st.divider()
st.subheader("Recent Orders")
ord_data = sb.table("sales_orders").select("*").order("created_at", desc=True).limit(20).execute().data
if ord_data:
    st.dataframe(pd.DataFrame(ord_data)[["created_at","customer_name","status","total_amount","deposit_paid","balance_due"]], use_container_width=True, hide_index=True)
