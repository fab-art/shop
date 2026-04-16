# Curtain Shop ERP

A complete ERP system for curtain shops built with FastAPI (backend), Streamlit (frontend), and Supabase (database).

## Features

- **Point of Sale (POS)**: Create sales, manage cart, track orders
- **Inventory Management**: Real-time stock tracking, purchase order receiving, stock adjustments
- **Finance & Reports**: Sales and purchase reports with analytics
- **Customer Tracking**: Public order tracking endpoint
- **Landed Cost Calculation**: Automatic allocation of shipping and other costs to inventory

## File Structure

```
project/
├── schema.sql              ← Run on Supabase
├── backend/
│   ├── main.py             ← FastAPI app
│   ├── requirements.txt
│   └── render.yaml
└── frontend/
    ├── Home.py             ← Streamlit entry
    ├── requirements.txt
    ├── .streamlit/
    │   └── secrets.toml.example
    └── pages/
        ├── 1_POS.py
        ├── 2_Inventory.py
        └── 3_Finance.py
```

## Deployment Guide

### Step 1: Supabase (Database)

1. Create free account at [supabase.com](https://supabase.com)
2. New project → SQL Editor → paste `schema.sql` → Run
3. Copy your **Project URL** and **anon key** from Settings > API

### Step 2: Render (Backend API)

1. Push `backend/` folder to a GitHub repo
2. New Web Service on [render.com](https://render.com) → connect repo
3. Set environment variables:
   - `SUPABASE_URL` = your Supabase URL
   - `SUPABASE_KEY` = your Supabase anon key
4. Deploy. Copy your Render URL (e.g. `https://curtain-shop-api.onrender.com`)

### Step 3: Streamlit Cloud (Frontend)

1. Push `frontend/` folder to a GitHub repo (can be same repo, different folder)
2. New app on [share.streamlit.io](https://share.streamlit.io) → set main file: `Home.py`
3. Add secrets:
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key-here"
   API_URL = "https://curtain-shop-api.onrender.com"
   ```
4. Deploy.

## Notes

- **Cold start on Render**: First request of the day takes ~30–50 seconds. This is expected.
- **Current Inventory View**: Auto-calculates stock from the ledger table.
- **Landed Cost**: Uses moving average when receiving additional stock.
- **Customer Tracking URL**: `https://your-render-url/track/{order_id}`

## API Endpoints

### Products
- `GET /products` - List all products
- `POST /products` - Create product
- `PUT /products/{id}` - Update product
- `DELETE /products/{id}` - Delete product

### Customers
- `GET /customers` - List all customers
- `POST /customers` - Create customer

### Suppliers
- `GET /suppliers` - List all suppliers
- `POST /suppliers` - Create supplier

### Inventory
- `GET /inventory` - Get current inventory levels
- `POST /inventory/adjust` - Manual stock adjustment

### Sales Orders
- `GET /sales-orders` - List sales orders
- `POST /sales-orders` - Create new sale
- `PATCH /sales-orders/{id}/status` - Update order status
- `GET /track/{order_id}` - Public order tracking

### Purchase Orders
- `GET /purchase-orders` - List purchase orders
- `POST /purchase-orders` - Create purchase order
- `POST /purchase-orders/{id}/receive` - Receive order into inventory

### Dashboard
- `GET /dashboard/stats` - Get summary statistics

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
export SUPABASE_URL="your-url"
export SUPABASE_KEY="your-key"
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
pip install -r requirements.txt
# Create .streamlit/secrets.toml with your credentials
streamlit run Home.py
```