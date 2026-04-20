# Curtain ERP (Streamlit + Supabase)

Production-ready ERP + POS system built with:

- **Frontend:** Streamlit multipage app
- **Database/Auth/Security:** Supabase (Postgres + Auth + RLS)
- **Language:** Python

## App Structure

```txt
.
├── main.py
├── pages/
│   ├── 1_POS.py
│   ├── 2_Inventory.py
│   ├── 3_Finance.py
│   ├── 4_Orders.py
│   └── 5_Admin.py
├── app/
│   ├── core.py
│   └── ui.py
├── schema.sql
└── requirements.txt
```

## Features

### Authentication
- Login / Signup / Logout via Supabase Auth
- Profile bootstrapping in `profiles` table
- Role-based access (`admin`, `cashier`)

### POS
- Product select + auto price
- Decimal quantity support
- Cart in session state
- Checkout creates:
  - `sales_orders`
  - `order_lines`
  - inventory ledger `SALE` entries

### Inventory
- Live stock computed from ledger sum
- KPIs (item count, low stock, value)
- Stock inward with landed-cost weighted averaging
- Admin-only adjustment entries (`ADJUSTMENT`) with reason

### Finance (Admin)
- Revenue, COGS, Gross Profit, Expenses, Net Profit
- Accounts payable from unpaid purchase invoices
- Expense logging

### Orders
- Sales order list + order lines (view-only)
- Admin status updates with cancellation inventory reversal

### Admin
- Edit catalog
- Edit purchase invoices (recalculate landed cost)
- Edit/delete expenses
- All updates/deletes logged to `audit_logs`

## UI Design

A custom dark/gold design system is injected via `st.markdown(<style>...</style>, unsafe_allow_html=True)`.

## Setup

1. Create Supabase project.
2. Run `schema.sql` in Supabase SQL Editor.
3. Configure Streamlit secrets or env vars:

```toml
SUPABASE_URL = "https://<project>.supabase.co"
SUPABASE_KEY = "<anon-key>"
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run app:

```bash
streamlit run main.py
```

## Streamlit Cloud

This system is designed to run on Streamlit Cloud + Supabase Free Tier only.
