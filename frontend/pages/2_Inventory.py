import streamlit as st
import requests

# Page configuration
st.set_page_config(
    page_title="Inventory - Curtain Shop",
    page_icon="📦",
    layout="wide"
)

# API URL from secrets
API_URL = st.secrets.get("API_URL", "http://localhost:8000")

# Helper functions
def fetch_from_api(endpoint):
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

def post_to_api(endpoint, data):
    try:
        response = requests.post(f"{API_URL}{endpoint}", json=data, timeout=10)
        if response.status_code in [200, 201]:
            return response.json()
        st.error(f"API Error: {response.text}")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

st.title("📦 Inventory Management")

tab1, tab2, tab3 = st.tabs(["Current Stock", "Receive Purchase Order", "Adjust Stock"])

with tab1:
    st.subheader("Current Inventory Levels")
    
    inventory = fetch_from_api("/inventory")
    if inventory:
        st.dataframe(inventory, use_container_width=True)
    else:
        st.info("No inventory data available")

with tab2:
    st.subheader("Receive Purchase Order")
    
    pos = fetch_from_api("/purchase-orders?status_filter=pending")
    if pos:
        po_options = {f"{po['order_number']} - {po['suppliers']['name']}": po['id'] for po in pos}
        selected_po = st.selectbox("Select Purchase Order", list(po_options.keys()))
        
        if selected_po and st.button("Receive Order"):
            po_id = po_options[selected_po]
            result = post_to_api(f"/purchase-orders/{po_id}/receive", {})
            if result:
                st.success("Purchase order received successfully!")
                st.rerun()
    else:
        st.info("No pending purchase orders")

with tab3:
    st.subheader("Manual Stock Adjustment")
    
    products = fetch_from_api("/products") or []
    
    col1, col2 = st.columns(2)
    with col1:
        product_id = st.selectbox(
            "Product",
            options=[p['id'] for p in products],
            format_func=lambda x: next((p['name'] for p in products if p['id'] == x), "Select Product")
        )
    with col2:
        adjustment_qty = st.number_input("Adjustment Quantity (+/-)", value=0.0)
    
    notes = st.text_area("Notes (optional)")
    
    if st.button("Submit Adjustment"):
        data = {
            "product_id": product_id,
            "quantity": adjustment_qty,
            "notes": notes
        }
        result = post_to_api("/inventory/adjust", data)
        if result:
            st.success("Inventory adjusted successfully!")
