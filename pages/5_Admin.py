import pandas as pd
import streamlit as st

from app.core import get_supabase, init_session_state, log_audit, require_admin, safe_float
from app.ui import inject_design_system

st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
inject_design_system()
init_session_state()
require_admin()
sb = get_supabase()

st.title("🛠️ Admin Controls")

# Catalog editing
st.subheader("Catalog")
catalog = sb.table("catalog").select("*").order("name").execute().data or []
st.dataframe(pd.DataFrame(catalog), use_container_width=True)

if catalog:
    with st.expander("Edit Catalog Record"):
        with st.form("catalog_form"):
            picks = {f"{x['name']} ({x['item_id'][:8]})": x for x in catalog}
            selected = st.selectbox("Record", list(picks.keys()))
            row = picks[selected]
            name = st.text_input("Name", value=row.get("name", ""))
            item_type = st.text_input("Type", value=row.get("type", ""))
            uom = st.text_input("UOM", value=row.get("uom", ""))
            landed = st.number_input("Current Landed Cost", min_value=0.0, value=safe_float(row.get("current_landed_cost")))
            sell = st.number_input("Default Sell Price", min_value=0.0, value=safe_float(row.get("default_sell_price")))
            submit = st.form_submit_button("Save")
            if submit:
                if not name.strip() or not item_type.strip() or not uom.strip():
                    st.error("Required fields missing")
                    st.stop()
                patch = {
                    "name": name.strip(),
                    "type": item_type.strip(),
                    "uom": uom.strip(),
                    "current_landed_cost": landed,
                    "default_sell_price": sell,
                }
                updated = sb.table("catalog").update(patch).eq("item_id", row["item_id"]).execute().data[0]
                log_audit(sb, "UPDATE", "catalog", row["item_id"], row, updated)
                st.success("Catalog updated")
                st.rerun()

st.divider()
# Purchase invoices edit
st.subheader("Purchase Invoices")
invoices = sb.table("purchase_invoices").select("*").order("created_at", desc=True).limit(300).execute().data or []
st.dataframe(pd.DataFrame(invoices), use_container_width=True)

if invoices:
    with st.expander("Edit Purchase Invoice"):
        with st.form("invoice_form"):
            picks = {f"{x['invoice_id'][:8]} · {x['status']}": x for x in invoices}
            selected = st.selectbox("Invoice", list(picks.keys()))
            row = picks[selected]
            status = st.selectbox("Status", ["Paid", "On Credit"], index=0 if row.get("status") == "Paid" else 1)
            supplier_id = st.text_input("Supplier ID", value=row.get("supplier_id") or "")
            purchase_price = st.number_input("Purchase Price", min_value=0.0, value=safe_float(row.get("purchase_price")))
            freight_cost = st.number_input("Freight Cost", min_value=0.0, value=safe_float(row.get("freight_cost")))
            submit = st.form_submit_button("Save")
            if submit:
                qty = safe_float(row.get("quantity"))
                landed = (purchase_price + freight_cost) / qty if qty > 0 else 0
                patch = {
                    "status": status,
                    "supplier_id": supplier_id or None,
                    "purchase_price": purchase_price,
                    "freight_cost": freight_cost,
                    "landed_cost": landed,
                }
                updated = sb.table("purchase_invoices").update(patch).eq("invoice_id", row["invoice_id"]).execute().data[0]
                log_audit(sb, "UPDATE", "purchase_invoices", row["invoice_id"], row, updated)

                if qty > 0:
                    cat = sb.table("catalog").select("current_landed_cost").eq("item_id", row["item_id"]).execute().data
                    old_cost = safe_float(cat[0]["current_landed_cost"]) if cat else 0
                    led = sb.table("inventory_ledger").select("quantity_change").eq("item_id", row["item_id"]).execute().data or []
                    old_qty = max(sum(safe_float(x["quantity_change"]) for x in led), 0)
                    new_avg = ((old_qty * old_cost) + (qty * landed)) / (old_qty + qty) if (old_qty + qty) > 0 else landed
                    sb.table("catalog").update({"current_landed_cost": round(new_avg, 2)}).eq("item_id", row["item_id"]).execute()

                st.success("Invoice updated")
                st.rerun()

st.divider()
# Expenses edit/delete
st.subheader("Expenses")
expenses = sb.table("expenses").select("*").order("expense_date", desc=True).limit(300).execute().data or []
st.dataframe(pd.DataFrame(expenses), use_container_width=True)

if expenses:
    with st.expander("Edit/Delete Expense"):
        with st.form("expense_admin_form"):
            picks = {f"{x['expense_id'][:8]} · {x['description']}": x for x in expenses}
            selected = st.selectbox("Expense", list(picks.keys()))
            row = picks[selected]
            description = st.text_input("Description", value=row.get("description", ""))
            amount = st.number_input("Amount", min_value=0.0, value=safe_float(row.get("amount")))
            category = st.text_input("Category", value=row.get("category", ""))
            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Save")
            delete = c2.form_submit_button("Delete")
            if save:
                patch = {"description": description.strip(), "amount": amount, "category": category.strip()}
                updated = sb.table("expenses").update(patch).eq("expense_id", row["expense_id"]).execute().data[0]
                log_audit(sb, "UPDATE", "expenses", row["expense_id"], row, updated)
                st.success("Expense updated")
                st.rerun()
            if delete:
                sb.table("expenses").delete().eq("expense_id", row["expense_id"]).execute()
                log_audit(sb, "DELETE", "expenses", row["expense_id"], row, {})
                st.success("Expense deleted")
                st.rerun()
