import streamlit as st
from supabase import create_client, Client
import requests
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Curtain Shop ERP",
    page_icon="🏪",
    layout="wide"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)
    return None

supabase = init_supabase()

# API URL from secrets
API_URL = st.secrets.get("API_URL", "http://localhost:8000")

# Helper functions
def fetch_from_api(endpoint):
    """Fetch data from the backend API."""
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

def post_to_api(endpoint, data):
    """Post data to the backend API."""
    try:
        response = requests.post(f"{API_URL}{endpoint}", json=data, timeout=10)
        if response.status_code in [200, 201]:
            return response.json()
        st.error(f"API Error: {response.text}")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

# Sidebar navigation
st.sidebar.title("🏪 Curtain Shop ERP")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "POS (Point of Sale)", "Inventory Management", "Finance & Reports"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Stats")

# Display quick stats if API is available
try:
    stats = fetch_from_api("/dashboard/stats")
    if stats:
        st.sidebar.metric("Products", stats.get('total_products', 0))
        st.sidebar.metric("Inventory Value", f"${stats.get('inventory_value', 0):,.2f}")
        st.sidebar.metric("Pending SO", stats.get('pending_sales_orders', 0))
        st.sidebar.metric("Pending PO", stats.get('pending_purchase_orders', 0))
except:
    st.sidebar.info("Connect API for live stats")

st.sidebar.markdown("---")
st.sidebar.caption(f"API: {API_URL}")

# Main content based on selection
if page == "Dashboard":
    st.title("📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Products", "Loading...")
    
    with col2:
        st.metric("Inventory Value", "Loading...")
    
    with col3:
        st.metric("Pending Orders", "Loading...")
    
    with col4:
        st.metric("Today's Sales", "Loading...")
    
    st.markdown("---")
    
    # Recent activity section
    st.subheader("Recent Activity")
    
    try:
        sales_orders = fetch_from_api("/sales-orders?status_filter=pending")
        if sales_orders:
            st.write("**Pending Sales Orders:**")
            for order in sales_orders[:5]:
                st.write(f"- {order.get('order_number', 'N/A')}: ${order.get('total_amount', 0):.2f}")
    except:
        st.info("No recent orders found or API not connected")
    
    st.markdown("---")
    
    # System status
    st.subheader("System Status")
    try:
        health = fetch_from_api("/health")
        if health:
            st.success("✅ Backend API Connected")
            st.json(health)
        else:
            st.warning("⚠️ Backend API Not Responding")
    except:
        st.error("❌ Cannot connect to backend API")

elif page == "POS (Point of Sale)":
    st.title("💰 Point of Sale")
    
    tab1, tab2 = st.tabs(["New Sale", "Order History"])
    
    with tab1:
        st.subheader("Create New Sale")
        
        # Customer selection
        customers = []
        try:
            customers = fetch_from_api("/customers") or []
        except:
            pass
        
        customer_options = ["Walk-in Customer"] + [c['name'] for c in customers]
        selected_customer = st.selectbox("Customer", customer_options)
        
        # Product selection
        products = []
        try:
            products = fetch_from_api("/products") or []
        except:
            pass
        
        st.subheader("Add Items")
        
        # Session state for cart
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
        
        # Display cart
        if st.session_state.cart:
            st.subheader("Shopping Cart")
            cart_df = st.session_state.cart
            
            for i, item in enumerate(cart_df):
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].write(item['product_name'])
                cols[1].write(f"{item['quantity']}")
                cols[2].write(f"${item['unit_price']:.2f}")
                cols[3].write(f"${item['quantity'] * item['unit_price']:.2f}")
                if cols[4].button("Remove", key=f"remove_{i}"):
                    st.session_state.cart.pop(i)
                    st.rerun()
            
            total = sum(item['quantity'] * item['unit_price'] for item in cart_df)
            st.markdown(f"### Total: ${total:.2f}")
            
            if st.button("Complete Sale", type="primary"):
                # Prepare order data
                order_data = {
                    "items": [
                        {
                            "product_id": item['product_id'],
                            "quantity": item['quantity'],
                            "unit_price": item['unit_price']
                        }
                        for item in cart_df
                    ]
                }
                
                result = post_to_api("/sales-orders", order_data)
                if result:
                    st.success(f"Order created: {result.get('order_number', 'N/A')}")
                    st.session_state.cart = []
                    st.rerun()
    
    with tab2:
        st.subheader("Recent Orders")
        try:
            orders = fetch_from_api("/sales-orders")
            if orders:
                for order in orders[:10]:
                    with st.expander(f"{order.get('order_number', 'N/A')} - ${order.get('total_amount', 0):.2f}"):
                        st.write(f"**Status:** {order.get('status', 'unknown')}")
                        st.write(f"**Date:** {order.get('order_date', 'N/A')}")
                        st.write(f"**Customer:** {order.get('customers', {}).get('name', 'Walk-in')}")
        except:
            st.info("No orders found")

elif page == "Inventory Management":
    st.title("📦 Inventory Management")
    
    tab1, tab2, tab3 = st.tabs(["Current Stock", "Receive Purchase Order", "Adjust Stock"])
    
    with tab1:
        st.subheader("Current Inventory Levels")
        
        try:
            inventory = fetch_from_api("/inventory")
            if inventory:
                st.dataframe(inventory, use_container_width=True)
            else:
                st.info("No inventory data available")
        except:
            st.error("Could not fetch inventory data")
    
    with tab2:
        st.subheader("Receive Purchase Order")
        
        try:
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
        except:
            st.error("Could not fetch purchase orders")
    
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

elif page == "Finance & Reports":
    st.title("💵 Finance & Reports")
    
    tab1, tab2 = st.tabs(["Sales Report", "Purchase Report"])
    
    with tab1:
        st.subheader("Sales Summary")
        
        try:
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
        except:
            st.info("No sales data available")
    
    with tab2:
        st.subheader("Purchase Summary")
        
        try:
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
        except:
            st.info("No purchase data available")

# Footer
st.markdown("---")
st.caption("Curtain Shop ERP v1.0 | Built with Streamlit & FastAPI")
