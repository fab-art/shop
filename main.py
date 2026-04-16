from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client
import os

app = FastAPI(title="Curtain Shop ERP")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Models ---
class OrderLine(BaseModel):
    item_id: str
    quantity: float
    unit_price: float

class CheckoutPayload(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = ""
    deposit_paid: float = 0
    lines: List[OrderLine]

class InwardPayload(BaseModel):
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    item_type: str = "Material"
    item_uom: str = "Meters"
    supplier_id: Optional[str] = None
    quantity: float
    purchase_price: float
    freight_cost: float = 0
    status: str = "On Credit"

class ExpensePayload(BaseModel):
    description: str
    amount: float
    category: str = "General"


# --- Checkout ---
@app.post("/api/orders/checkout")
def checkout(payload: CheckoutPayload):
    # Fetch landed costs for all items
    item_ids = [l.item_id for l in payload.lines]
    catalog = sb.table("catalog").select("item_id,current_landed_cost").in_("item_id", item_ids).execute()
    cost_map = {r["item_id"]: r["current_landed_cost"] for r in catalog.data}

    total = sum(l.quantity * l.unit_price for l in payload.lines)

    # Insert order
    order = sb.table("sales_orders").insert({
        "customer_name": payload.customer_name,
        "customer_phone": payload.customer_phone,
        "total_amount": total,
        "deposit_paid": payload.deposit_paid,
        "status": "Pending"
    }).execute()

    order_id = order.data[0]["order_id"]

    # Insert lines + ledger deductions
    for line in payload.lines:
        cogs = cost_map.get(line.item_id, 0) * line.quantity
        sb.table("order_lines").insert({
            "order_id": order_id,
            "item_id": line.item_id,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "line_cogs": cogs
        }).execute()
        sb.table("inventory_ledger").insert({
            "item_id": line.item_id,
            "transaction_type": "SALE",
            "quantity_change": -line.quantity,
            "unit_cost": cost_map.get(line.item_id, 0)
        }).execute()

    return {"order_id": order_id, "total": total, "balance_due": total - payload.deposit_paid}


# --- Inward Stock ---
@app.post("/api/inventory/inward")
def inward(payload: InwardPayload):
    try:
        landed_cost_per_unit = (payload.purchase_price + payload.freight_cost) / payload.quantity
        item_id = payload.item_id

        if not item_id:
            # New item
            res = sb.table("catalog").insert({
                "name": payload.item_name,
                "type": payload.item_type,
                "uom": payload.item_uom,
                "current_landed_cost": round(landed_cost_per_unit, 2),
                "default_sell_price": round(landed_cost_per_unit * 1.3, 2)
            }).execute()
            item_id = res.data[0]["item_id"]
        else:
            # Compute moving average from ledger directly (avoid view query issues)
            cat = sb.table("catalog").select("current_landed_cost").eq("item_id", item_id).execute()
            ledger = sb.table("inventory_ledger").select("quantity_change").eq("item_id", item_id).execute()

            old_qty = sum(r["quantity_change"] for r in ledger.data) if ledger.data else 0
            old_cost = cat.data[0]["current_landed_cost"] if cat.data else 0

            if old_qty + payload.quantity > 0:
                new_avg = ((old_qty * old_cost) + (payload.quantity * landed_cost_per_unit)) / (old_qty + payload.quantity)
            else:
                new_avg = landed_cost_per_unit

            sb.table("catalog").update({"current_landed_cost": round(new_avg, 2)}).eq("item_id", item_id).execute()

        # Ledger entry
        sb.table("inventory_ledger").insert({
            "item_id": item_id,
            "transaction_type": "INWARD",
            "quantity_change": payload.quantity,
            "unit_cost": round(landed_cost_per_unit, 2)
        }).execute()

        # Purchase invoice — only include supplier_id if provided
        invoice_data = {
            "item_id": item_id,
            "quantity": payload.quantity,
            "purchase_price": payload.purchase_price,
            "freight_cost": payload.freight_cost,
            "status": payload.status
        }
        if payload.supplier_id:
            invoice_data["supplier_id"] = payload.supplier_id

        sb.table("purchase_invoices").insert(invoice_data).execute()

        return {"item_id": item_id, "landed_cost_per_unit": round(landed_cost_per_unit, 2)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Expense Logger ---
@app.post("/api/expenses")
def log_expense(payload: ExpensePayload):
    res = sb.table("expenses").insert({
        "description": payload.description,
        "amount": payload.amount,
        "category": payload.category
    }).execute()
    return res.data[0]


# --- Order Tracking (Customer Portal) ---
@app.get("/track/{order_id}", response_class=HTMLResponse)
def track_order(order_id: str):
    order = sb.table("sales_orders").select("*").eq("order_id", order_id).execute()
    if not order.data:
        return HTMLResponse("<h2>Order not found.</h2>", status_code=404)
    o = order.data[0]
    lines = sb.table("order_lines").select("quantity,unit_price,catalog(name)").eq("order_id", order_id).execute()
    rows = "".join(
        f"<tr><td>{l['catalog']['name']}</td><td>{l['quantity']}</td><td>{l['unit_price']}</td></tr>"
        for l in lines.data
    )
    return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Order {order_id[:8]}</title>
<style>body{{font-family:sans-serif;max-width:480px;margin:auto;padding:16px}}
table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:8px}}
.badge{{background:#f0ad4e;padding:4px 10px;border-radius:12px;font-size:.85em}}</style></head>
<body>
<h2>Order Status</h2>
<p><strong>Customer:</strong> {o['customer_name']}</p>
<p><strong>Status:</strong> <span class='badge'>{o['status']}</span></p>
<table><tr><th>Item</th><th>Qty</th><th>Price</th></tr>{rows}</table>
<p><strong>Total:</strong> {o['total_amount']} &nbsp;|&nbsp; <strong>Deposit:</strong> {o['deposit_paid']} &nbsp;|&nbsp; <strong>Balance Due:</strong> {o['balance_due']}</p>
</body></html>
""")
