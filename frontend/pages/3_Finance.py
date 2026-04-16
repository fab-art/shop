import streamlit as st
import requests

# Page configuration
st.set_page_config(
    page_title="Finance - Curtain Shop",
    page_icon="💵",
    layout="wide"
)

# API URL from secrets
API_URL = st.secrets.get("API_URL", "http://localhost:8000")

# Helper function
def fetch_from_api(endpoint):
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

st.title("💵 Finance & Reports")

tab1, tab2 = st.tabs(["Sales Report", "Purchase Report"])

with tab1:
    st.subheader("Sales Summary")
    
    orders = fetch_from_api("/sales-orders")
    if orders:
        total_sales = sum(o.get('total_amount', 0) for o in orders)
        completed = len([o for o in orders if o.get('status') == 'completed'])
        pending = len([o for o in orders if o.get('status') == 'pending'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sales", f"${total_sales:.2f}")
        col2.metric("Completed Orders", completed)
        col3.metric("Pending Orders", pending)
        
        st.markdown("### Order Details")
        st.dataframe(orders, use_container_width=True)
    else:
        st.info("No sales data available")

with tab2:
    st.subheader("Purchase Summary")
    
    pos = fetch_from_api("/purchase-orders")
    if pos:
        total_purchases = sum(p.get('total_landed_cost', 0) for p in pos)
        received = len([p for p in pos if p.get('status') == 'received'])
        pending = len([p for p in pos if p.get('status') == 'pending'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Purchases", f"${total_purchases:.2f}")
        col2.metric("Received Orders", received)
        col3.metric("Pending Orders", pending)
        
        st.markdown("### Purchase Order Details")
        st.dataframe(pos, use_container_width=True)
    else:
        st.info("No purchase data available")
