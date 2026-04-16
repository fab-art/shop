import streamlit as st
import requests
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="POS - Curtain Shop",
    page_icon="💰",
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

st.title("💰 Point of Sale")

tab1, tab2 = st.tabs(["New Sale", "Order History"])

with tab1:
    st.subheader("Create New Sale")
    
    # Customer selection
    customers = fetch_from_api("/customers") or []
    customer_options = ["Walk-in Customer"] + [c['name'] for c in customers]
    selected_customer = st.selectbox("Customer", customer_options)
    
    # Product selection
    products = fetch_from_api("/products") or []
    
    st.subheader("Add Items")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    
    col1, col2, col3 = st.columns(3)
    with col1:
        product_select = st.selectbox(
            "Product", 
            options=[p['id'] for p in products],
            format_func=lambda x: next((p['name'] for p in products if p['id'] == x), "Select Product"),
            key="product_sel"
        )
    with col2:
        quantity = st.number_input("Quantity", min_value=0.01, value=1.0, key="qty")
    with col3:
        price = st.number_input("Unit Price ($)", min_value=0.0, value=0.0, key="price")
    
    if st.button("Add to Cart"):
        if product_select:
            product_name = next((p['name'] for p in products if p['id'] == product_select), "Unknown")
            st.session_state.cart.append({
                "product_id": product_select,
                "product_name": product_name,
                "quantity": quantity,
                "unit_price": price
            })
            st.success(f"Added {product_name} to cart")
    
    if st.session_state.cart:
        st.subheader("Shopping Cart")
        
        for i, item in enumerate(st.session_state.cart):
            cols = st.columns([3, 1, 1, 1, 1])
            cols[0].write(item['product_name'])
            cols[1].write(f"{item['quantity']}")
            cols[2].write(f"${item['unit_price']:.2f}")
            cols[3].write(f"${item['quantity'] * item['unit_price']:.2f}")
            if cols[4].button("Remove", key=f"remove_{i}"):
                st.session_state.cart.pop(i)
                st.rerun()
        
        total = sum(item['quantity'] * item['unit_price'] for item in st.session_state.cart)
        st.markdown(f"### Total: ${total:.2f}")
        
        if st.button("Complete Sale", type="primary"):
            order_data = {
                "items": [
                    {
                        "product_id": item['product_id'],
                        "quantity": item['quantity'],
                        "unit_price": item['unit_price']
                    }
                    for item in st.session_state.cart
                ]
            }
            
            result = post_to_api("/sales-orders", order_data)
            if result:
                st.success(f"Order created: {result.get('order_number', 'N/A')}")
                st.session_state.cart = []
                st.rerun()

with tab2:
    st.subheader("Recent Orders")
    orders = fetch_from_api("/sales-orders")
    if orders:
        for order in orders[:10]:
            with st.expander(f"{order.get('order_number', 'N/A')} - ${order.get('total_amount', 0):.2f}"):
                st.write(f"**Status:** {order.get('status', 'unknown')}")
                st.write(f"**Date:** {order.get('order_date', 'N/A')}")
                st.write(f"**Customer:** {order.get('customers', {}).get('name', 'Walk-in')}")
