import os
from supabase import create_client
import streamlit as st

@st.cache_resource
def get_sb():
    url = os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def load_inventory(sb):
    catalog = sb.table("catalog").select("item_id,name,type,uom,current_landed_cost,default_sell_price").execute().data
    ledger = sb.table("inventory_ledger").select("item_id,quantity_change").execute().data
    totals = {}
    for r in ledger:
        totals[r["item_id"]] = totals.get(r["item_id"], 0) + r["quantity_change"]
    for c in catalog:
        c["stock_on_hand"] = round(totals.get(c["item_id"], 0), 3)
    return catalog
