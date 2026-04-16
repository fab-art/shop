--- main.py (原始)
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import os
import uuid
from supabase import create_client, Client

# Initialize FastAPI app
app = FastAPI(title="Curtain Shop ERP API", version="1.0.0", root_path="/api")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Pydantic Models
class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: Optional[str] = "piece"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: Optional[str] = None


class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SalesOrderItemCreate(BaseModel):
    product_id: str
    quantity: Decimal
    unit_price: Decimal


class SalesOrderCreate(BaseModel):
    customer_id: Optional[str] = None
    status: Optional[str] = "pending"
    delivery_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[SalesOrderItemCreate] = []


class PurchaseOrderItemCreate(BaseModel):
    product_id: str
    quantity: Decimal
    unit_cost: Decimal


class PurchaseOrderCreate(BaseModel):
    supplier_id: Optional[str] = None
    status: Optional[str] = "pending"
    expected_date: Optional[date] = None
    shipping_cost: Optional[Decimal] = Decimal("0")
    other_costs: Optional[Decimal] = Decimal("0")
    items: List[PurchaseOrderItemCreate] = []


class InventoryAdjustment(BaseModel):
    product_id: str
    quantity: Decimal  # positive for in, negative for out
    transaction_type: str = "adjustment"
    notes: Optional[str] = None


# Helper functions
def generate_order_number(prefix: str) -> str:
    """Generate a unique order number."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{timestamp}-{random_suffix}"


def calculate_landed_cost_allocation(items: List[dict], total_additional_costs: Decimal) -> List[dict]:
    """Allocate additional costs proportionally based on item value."""
    total_value = sum(Decimal(item['quantity']) * Decimal(item['unit_cost']) for item in items)

    if total_value == 0:
        return items

    for item in items:
        line_total = Decimal(item['quantity']) * Decimal(item['unit_cost'])
        allocation_ratio = line_total / total_value
        allocated_cost = total_additional_costs * allocation_ratio
        item['allocated_landed_cost'] = float(allocated_cost)
        item['final_unit_cost'] = float((line_total + allocated_cost) / Decimal(item['quantity']))

    return items


# API Endpoints

@app.get("/")
async def root():
    return {"message": "Curtain Shop ERP API", "status": "running"}


@app.get("/api")
async def api_root():
    return {"message": "Curtain Shop ERP API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Products
@app.get("/products", tags=["Products"])
async def get_products():
    result = supabase.table("products").select("*").order("name").execute()
    return result.data


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: str):
    result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.data[0]


@app.post("/products", tags=["Products"])
async def create_product(product: ProductCreate):
    data = product.model_dump()
    result = supabase.table("products").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create product")
    return result.data[0]


@app.put("/products/{product_id}", tags=["Products"])
async def update_product(product_id: str, product: ProductUpdate):
    data = {k: v for k, v in product.model_dump().items() if v is not None}
    result = supabase.table("products").update(data).eq("id", product_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.data[0]


@app.delete("/products/{product_id}", tags=["Products"])
async def delete_product(product_id: str):
    result = supabase.table("products").delete().eq("id", product_id).execute()
    return {"message": "Product deleted successfully"}


# Customers
@app.get("/customers", tags=["Customers"])
async def get_customers():
    result = supabase.table("customers").select("*").order("name").execute()
    return result.data


@app.post("/customers", tags=["Customers"])
async def create_customer(customer: CustomerCreate):
    data = customer.model_dump()
    result = supabase.table("customers").insert(data).execute()
    return result.data[0]


# Suppliers
@app.get("/suppliers", tags=["Suppliers"])
async def get_suppliers():
    result = supabase.table("suppliers").select("*").order("name").execute()
    return result.data


@app.post("/suppliers", tags=["Suppliers"])
async def create_supplier(supplier: SupplierCreate):
    data = supplier.model_dump()
    result = supabase.table("suppliers").insert(data).execute()
    return result.data[0]


# Inventory
@app.get("/inventory", tags=["Inventory"])
async def get_inventory():
    result = supabase.rpc("current_inventory").execute()
    return result.data if result.data else []


@app.post("/inventory/adjust", tags=["Inventory"])
async def adjust_inventory(adjustment: InventoryAdjustment):
    # Get current average cost
    inv_result = supabase.table("current_inventory").select("average_cost").eq("product_id", adjustment.product_id).execute()
    unit_cost = Decimal(str(inv_result.data[0]['average_cost'])) if inv_result.data and inv_result.data[0]['average_cost'] else Decimal("0")

    # Create ledger entry
    ledger_data = {
        "product_id": adjustment.product_id,
        "transaction_type": adjustment.transaction_type,
        "quantity": float(adjustment.quantity),
        "unit_cost": float(unit_cost),
        "total_cost": float(adjustment.quantity * unit_cost),
        "notes": adjustment.notes
    }

    result = supabase.table("inventory_ledger").insert(ledger_data).execute()
    return result.data[0]


# Sales Orders
@app.get("/sales-orders", tags=["Sales Orders"])
async def get_sales_orders(status_filter: Optional[str] = None):
    query = supabase.table("sales_orders").select("*, customers(name)")
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.order("created_at", desc=True).execute()
    return result.data


@app.get("/sales-orders/{order_id}", tags=["Sales Orders"])
async def get_sales_order(order_id: str):
    result = supabase.table("sales_orders").select("*, sales_order_items(*, products(sku, name))").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.post("/sales-orders", tags=["Sales Orders"])
async def create_sales_order(order: SalesOrderCreate):
    # Generate order number
    order_number = generate_order_number("SO")

    # Calculate totals
    subtotal = sum(item.quantity * item.unit_price for item in order.items)
    tax_amount = subtotal * Decimal("0.10")  # 10% tax (adjust as needed)
    total_amount = subtotal + tax_amount

    # Create order
    order_data = {
        "order_number": order_number,
        "customer_id": order.customer_id,
        "status": order.status,
        "delivery_date": str(order.delivery_date) if order.delivery_date else None,
        "notes": order.notes,
        "subtotal": float(subtotal),
        "tax_amount": float(tax_amount),
        "total_amount": float(total_amount)
    }

    result = supabase.table("sales_orders").insert(order_data).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create order")

    order_id = result.data[0]['id']

    # Create order items
    for item in order.items:
        item_data = {
            "order_id": order_id,
            "product_id": item.product_id,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "line_total": float(item.quantity * item.unit_price)
        }
        supabase.table("sales_order_items").insert(item_data).execute()

    # Deduct from inventory
    for item in order.items:
        ledger_data = {
            "product_id": item.product_id,
            "transaction_type": "sale",
            "quantity": float(-item.quantity),
            "unit_cost": 0,
            "total_cost": 0,
            "reference_id": order_id
        }
        supabase.table("inventory_ledger").insert(ledger_data).execute()

    return supabase.table("sales_orders").select("*, sales_order_items(*)").eq("id", order_id).execute().data[0]


@app.patch("/sales-orders/{order_id}/status", tags=["Sales Orders"])
async def update_sales_order_status(order_id: str, status: str):
    result = supabase.table("sales_orders").update({"status": status}).eq("id", order_id).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.get("/track/{order_id}", tags=["Tracking"])
async def track_order(order_id: str):
    """Public endpoint for customers to track their orders."""
    result = supabase.table("sales_orders").select("order_number, status, order_date, delivery_date, total_amount, customers(name, phone)").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = result.data[0]
    items_result = supabase.table("sales_order_items").select("quantity, unit_price, line_total, products(sku, name)").eq("order_id", order_id).execute()
    order["items"] = items_result.data

    return order


# Purchase Orders
@app.get("/purchase-orders", tags=["Purchase Orders"])
async def get_purchase_orders(status_filter: Optional[str] = None):
    query = supabase.table("purchase_orders").select("*, suppliers(name)")
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.order("created_at", desc=True).execute()
    return result.data


@app.get("/purchase-orders/{order_id}", tags=["Purchase Orders"])
async def get_purchase_order(order_id: str):
    result = supabase.table("purchase_orders").select("*, purchase_order_items(*, products(sku, name))").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.post("/purchase-orders", tags=["Purchase Orders"])
async def create_purchase_order(order: PurchaseOrderCreate):
    # Generate order number
    order_number = generate_order_number("PO")

    # Calculate totals
    subtotal = sum(item.quantity * item.unit_cost for item in order.items)
    total_landed_cost = subtotal + order.shipping_cost + order.other_costs

    # Prepare items with landed cost allocation
    items_data = []
    additional_costs = order.shipping_cost + order.other_costs

    if additional_costs > 0:
        temp_items = [{"quantity": float(item.quantity), "unit_cost": float(item.unit_cost)} for item in order.items]
        temp_items = calculate_landed_cost_allocation(temp_items, additional_costs)

        for i, item in enumerate(order.items):
            items_data.append({
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_cost": float(item.unit_cost),
                "line_total": float(item.quantity * item.unit_cost),
                "allocated_landed_cost": temp_items[i]['allocated_landed_cost'],
                "final_unit_cost": temp_items[i]['final_unit_cost']
            })
    else:
        for item in order.items:
            items_data.append({
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_cost": float(item.unit_cost),
                "line_total": float(item.quantity * item.unit_cost),
                "allocated_landed_cost": 0,
                "final_unit_cost": float(item.unit_cost)
            })

    # Create order
    order_data = {
        "order_number": order_number,
        "supplier_id": order.supplier_id,
        "status": order.status,
        "expected_date": str(order.expected_date) if order.expected_date else None,
        "shipping_cost": float(order.shipping_cost),
        "other_costs": float(order.other_costs),
        "subtotal": float(subtotal),
        "total_landed_cost": float(total_landed_cost)
    }

    result = supabase.table("purchase_orders").insert(order_data).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create order")

    order_id = result.data[0]['id']

    # Create order items
    for item_data in items_data:
        item_data["order_id"] = order_id
        supabase.table("purchase_order_items").insert(item_data).execute()

    return supabase.table("purchase_orders").select("*, purchase_order_items(*)").eq("id", order_id).execute().data[0]


@app.post("/purchase-orders/{order_id}/receive", tags=["Purchase Orders"])
async def receive_purchase_order(order_id: str):
    """Receive a purchase order and add items to inventory."""
    # Get order details
    order_result = supabase.table("purchase_orders").select("*, purchase_order_items(*)").eq("id", order_id).execute()
    if not order_result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_result.data[0]

    if order['status'] == 'received':
        raise HTTPException(status_code=400, detail="Order already received")

    # Add to inventory ledger
    for item in order['purchase_order_items']:
        final_cost = Decimal(str(item['final_unit_cost'])) if item['final_unit_cost'] else Decimal(str(item['unit_cost']))
        quantity = Decimal(str(item['quantity']))

        ledger_data = {
            "product_id": item['product_id'],
            "transaction_type": "purchase",
            "quantity": float(quantity),
            "unit_cost": float(final_cost),
            "total_cost": float(quantity * final_cost),
            "reference_id": order_id
        }
        supabase.table("inventory_ledger").insert(ledger_data).execute()

    # Update order status
    result = supabase.table("purchase_orders").update({"status": "received"}).eq("id", order_id).select("*").execute()
    return result.data[0]


# Dashboard/Stats
@app.get("/dashboard/stats", tags=["Dashboard"])
async def get_dashboard_stats():
    # Get inventory summary
    inventory_result = supabase.table("current_inventory").select("*").execute()
    total_items = len(inventory_result.data) if inventory_result.data else 0
    total_value = sum(Decimal(str(item['inventory_value'])) for item in (inventory_result.data or []))

    # Get pending orders count
    pending_so = supabase.table("sales_orders").select("id", count="exact").eq("status", "pending").execute()
    pending_po = supabase.table("purchase_orders").select("id", count="exact").eq("status", "pending").execute()

    return {
        "total_products": total_items,
        "inventory_value": float(total_value),
        "pending_sales_orders": pending_so.count,
        "pending_purchase_orders": pending_po.count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

+++ main.py (修改后)
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import os
import uuid
from supabase import create_client, Client

# Initialize FastAPI app
app = FastAPI(title="Curtain Shop ERP API", version="1.0.0", root_path="/api")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Pydantic Models
class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: Optional[str] = "piece"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: Optional[str] = None


class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SalesOrderItemCreate(BaseModel):
    product_id: str
    quantity: Decimal
    unit_price: Decimal


class SalesOrderCreate(BaseModel):
    customer_id: Optional[str] = None
    status: Optional[str] = "pending"
    delivery_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[SalesOrderItemCreate] = []


class PurchaseOrderItemCreate(BaseModel):
    product_id: str
    quantity: Decimal
    unit_cost: Decimal


class PurchaseOrderCreate(BaseModel):
    supplier_id: Optional[str] = None
    status: Optional[str] = "pending"
    expected_date: Optional[date] = None
    shipping_cost: Optional[Decimal] = Decimal("0")
    other_costs: Optional[Decimal] = Decimal("0")
    items: List[PurchaseOrderItemCreate] = []


class InventoryAdjustment(BaseModel):
    product_id: str
    quantity: Decimal  # positive for in, negative for out
    transaction_type: str = "adjustment"
    notes: Optional[str] = None


# Helper functions
def generate_order_number(prefix: str) -> str:
    """Generate a unique order number."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{timestamp}-{random_suffix}"


def calculate_landed_cost_allocation(items: List[dict], total_additional_costs: Decimal) -> List[dict]:
    """Allocate additional costs proportionally based on item value."""
    total_value = sum(Decimal(item['quantity']) * Decimal(item['unit_cost']) for item in items)

    if total_value == 0:
        return items

    for item in items:
        line_total = Decimal(item['quantity']) * Decimal(item['unit_cost'])
        allocation_ratio = line_total / total_value
        allocated_cost = total_additional_costs * allocation_ratio
        item['allocated_landed_cost'] = float(allocated_cost)
        item['final_unit_cost'] = float((line_total + allocated_cost) / Decimal(item['quantity']))

    return items


# API Endpoints

@app.get("/")
async def root():
    return {"message": "Curtain Shop ERP API", "status": "running"}


@app.get("/api")
async def api_root():
    return {"message": "Curtain Shop ERP API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Products
@app.get("/products", tags=["Products"])
async def get_products():
    result = supabase.table("products").select("*").order("name").execute()
    return result.data


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: str):
    result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.data[0]


@app.post("/products", tags=["Products"])
async def create_product(product: ProductCreate):
    data = product.model_dump()
    result = supabase.table("products").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create product")
    return result.data[0]


@app.put("/products/{product_id}", tags=["Products"])
async def update_product(product_id: str, product: ProductUpdate):
    data = {k: v for k, v in product.model_dump().items() if v is not None}
    result = supabase.table("products").update(data).eq("id", product_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.data[0]


@app.delete("/products/{product_id}", tags=["Products"])
async def delete_product(product_id: str):
    result = supabase.table("products").delete().eq("id", product_id).execute()
    return {"message": "Product deleted successfully"}


# Customers
@app.get("/customers", tags=["Customers"])
async def get_customers():
    result = supabase.table("customers").select("*").order("name").execute()
    return result.data


@app.post("/customers", tags=["Customers"])
async def create_customer(customer: CustomerCreate):
    data = customer.model_dump()
    result = supabase.table("customers").insert(data).execute()
    return result.data[0]


# Suppliers
@app.get("/suppliers", tags=["Suppliers"])
async def get_suppliers():
    result = supabase.table("suppliers").select("*").order("name").execute()
    return result.data


@app.post("/suppliers", tags=["Suppliers"])
async def create_supplier(supplier: SupplierCreate):
    data = supplier.model_dump()
    result = supabase.table("suppliers").insert(data).execute()
    return result.data[0]


# Inventory
@app.get("/inventory", tags=["Inventory"])
async def get_inventory():
    result = supabase.rpc("current_inventory").execute()
    return result.data if result.data else []


@app.post("/inventory/adjust", tags=["Inventory"])
async def adjust_inventory(adjustment: InventoryAdjustment):
    # Get current average cost
    inv_result = supabase.table("current_inventory").select("average_cost").eq("product_id", adjustment.product_id).execute()
    unit_cost = Decimal(str(inv_result.data[0]['average_cost'])) if inv_result.data and inv_result.data[0]['average_cost'] else Decimal("0")

    # Create ledger entry
    ledger_data = {
        "product_id": adjustment.product_id,
        "transaction_type": adjustment.transaction_type,
        "quantity": float(adjustment.quantity),
        "unit_cost": float(unit_cost),
        "total_cost": float(adjustment.quantity * unit_cost),
        "notes": adjustment.notes
    }

    result = supabase.table("inventory_ledger").insert(ledger_data).execute()
    return result.data[0]


@app.post("/inventory/inward", tags=["Inventory"])
async def inventory_inward(adjustment: InventoryAdjustment):
    """Alias for adjust_inventory with positive quantity for inward stock movement."""
    # Ensure quantity is positive for inward movement
    if adjustment.quantity < 0:
        adjustment.quantity = abs(adjustment.quantity)

    # Set transaction type to 'inward' if not specified
    if adjustment.transaction_type == "adjustment":
        adjustment.transaction_type = "inward"

    # Get current average cost
    inv_result = supabase.table("current_inventory").select("average_cost").eq("product_id", adjustment.product_id).execute()
    unit_cost = Decimal(str(inv_result.data[0]['average_cost'])) if inv_result.data and inv_result.data[0]['average_cost'] else Decimal("0")

    # Create ledger entry
    ledger_data = {
        "product_id": adjustment.product_id,
        "transaction_type": adjustment.transaction_type,
        "quantity": float(adjustment.quantity),
        "unit_cost": float(unit_cost),
        "total_cost": float(adjustment.quantity * unit_cost),
        "notes": adjustment.notes
    }

    result = supabase.table("inventory_ledger").insert(ledger_data).execute()
    return result.data[0]


# Sales Orders
@app.get("/sales-orders", tags=["Sales Orders"])
async def get_sales_orders(status_filter: Optional[str] = None):
    query = supabase.table("sales_orders").select("*, customers(name)")
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.order("created_at", desc=True).execute()
    return result.data


@app.get("/sales-orders/{order_id}", tags=["Sales Orders"])
async def get_sales_order(order_id: str):
    result = supabase.table("sales_orders").select("*, sales_order_items(*, products(sku, name))").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.post("/sales-orders", tags=["Sales Orders"])
async def create_sales_order(order: SalesOrderCreate):
    # Generate order number
    order_number = generate_order_number("SO")

    # Calculate totals
    subtotal = sum(item.quantity * item.unit_price for item in order.items)
    tax_amount = subtotal * Decimal("0.10")  # 10% tax (adjust as needed)
    total_amount = subtotal + tax_amount

    # Create order
    order_data = {
        "order_number": order_number,
        "customer_id": order.customer_id,
        "status": order.status,
        "delivery_date": str(order.delivery_date) if order.delivery_date else None,
        "notes": order.notes,
        "subtotal": float(subtotal),
        "tax_amount": float(tax_amount),
        "total_amount": float(total_amount)
    }

    result = supabase.table("sales_orders").insert(order_data).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create order")

    order_id = result.data[0]['id']

    # Create order items
    for item in order.items:
        item_data = {
            "order_id": order_id,
            "product_id": item.product_id,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "line_total": float(item.quantity * item.unit_price)
        }
        supabase.table("sales_order_items").insert(item_data).execute()

    # Deduct from inventory
    for item in order.items:
        ledger_data = {
            "product_id": item.product_id,
            "transaction_type": "sale",
            "quantity": float(-item.quantity),
            "unit_cost": 0,
            "total_cost": 0,
            "reference_id": order_id
        }
        supabase.table("inventory_ledger").insert(ledger_data).execute()

    return supabase.table("sales_orders").select("*, sales_order_items(*)").eq("id", order_id).execute().data[0]


@app.patch("/sales-orders/{order_id}/status", tags=["Sales Orders"])
async def update_sales_order_status(order_id: str, status: str):
    result = supabase.table("sales_orders").update({"status": status}).eq("id", order_id).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.get("/track/{order_id}", tags=["Tracking"])
async def track_order(order_id: str):
    """Public endpoint for customers to track their orders."""
    result = supabase.table("sales_orders").select("order_number, status, order_date, delivery_date, total_amount, customers(name, phone)").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = result.data[0]
    items_result = supabase.table("sales_order_items").select("quantity, unit_price, line_total, products(sku, name)").eq("order_id", order_id).execute()
    order["items"] = items_result.data

    return order


# Purchase Orders
@app.get("/purchase-orders", tags=["Purchase Orders"])
async def get_purchase_orders(status_filter: Optional[str] = None):
    query = supabase.table("purchase_orders").select("*, suppliers(name)")
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.order("created_at", desc=True).execute()
    return result.data


@app.get("/purchase-orders/{order_id}", tags=["Purchase Orders"])
async def get_purchase_order(order_id: str):
    result = supabase.table("purchase_orders").select("*, purchase_order_items(*, products(sku, name))").eq("id", order_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data[0]


@app.post("/purchase-orders", tags=["Purchase Orders"])
async def create_purchase_order(order: PurchaseOrderCreate):
    # Generate order number
    order_number = generate_order_number("PO")

    # Calculate totals
    subtotal = sum(item.quantity * item.unit_cost for item in order.items)
    total_landed_cost = subtotal + order.shipping_cost + order.other_costs

    # Prepare items with landed cost allocation
    items_data = []
    additional_costs = order.shipping_cost + order.other_costs

    if additional_costs > 0:
        temp_items = [{"quantity": float(item.quantity), "unit_cost": float(item.unit_cost)} for item in order.items]
        temp_items = calculate_landed_cost_allocation(temp_items, additional_costs)

        for i, item in enumerate(order.items):
            items_data.append({
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_cost": float(item.unit_cost),
                "line_total": float(item.quantity * item.unit_cost),
                "allocated_landed_cost": temp_items[i]['allocated_landed_cost'],
                "final_unit_cost": temp_items[i]['final_unit_cost']
            })
    else:
        for item in order.items:
            items_data.append({
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_cost": float(item.unit_cost),
                "line_total": float(item.quantity * item.unit_cost),
                "allocated_landed_cost": 0,
                "final_unit_cost": float(item.unit_cost)
            })

    # Create order
    order_data = {
        "order_number": order_number,
        "supplier_id": order.supplier_id,
        "status": order.status,
        "expected_date": str(order.expected_date) if order.expected_date else None,
        "shipping_cost": float(order.shipping_cost),
        "other_costs": float(order.other_costs),
        "subtotal": float(subtotal),
        "total_landed_cost": float(total_landed_cost)
    }

    result = supabase.table("purchase_orders").insert(order_data).select("*").execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create order")

    order_id = result.data[0]['id']

    # Create order items
    for item_data in items_data:
        item_data["order_id"] = order_id
        supabase.table("purchase_order_items").insert(item_data).execute()

    return supabase.table("purchase_orders").select("*, purchase_order_items(*)").eq("id", order_id).execute().data[0]


@app.post("/purchase-orders/{order_id}/receive", tags=["Purchase Orders"])
async def receive_purchase_order(order_id: str):
    """Receive a purchase order and add items to inventory."""
    # Get order details
    order_result = supabase.table("purchase_orders").select("*, purchase_order_items(*)").eq("id", order_id).execute()
    if not order_result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_result.data[0]

    if order['status'] == 'received':
        raise HTTPException(status_code=400, detail="Order already received")

    # Add to inventory ledger
    for item in order['purchase_order_items']:
        final_cost = Decimal(str(item['final_unit_cost'])) if item['final_unit_cost'] else Decimal(str(item['unit_cost']))
        quantity = Decimal(str(item['quantity']))

        ledger_data = {
            "product_id": item['product_id'],
            "transaction_type": "purchase",
            "quantity": float(quantity),
            "unit_cost": float(final_cost),
            "total_cost": float(quantity * final_cost),
            "reference_id": order_id
        }
        supabase.table("inventory_ledger").insert(ledger_data).execute()

    # Update order status
    result = supabase.table("purchase_orders").update({"status": "received"}).eq("id", order_id).select("*").execute()
    return result.data[0]


# Dashboard/Stats
@app.get("/dashboard/stats", tags=["Dashboard"])
async def get_dashboard_stats():
    # Get inventory summary
    inventory_result = supabase.table("current_inventory").select("*").execute()
    total_items = len(inventory_result.data) if inventory_result.data else 0
    total_value = sum(Decimal(str(item['inventory_value'])) for item in (inventory_result.data or []))

    # Get pending orders count
    pending_so = supabase.table("sales_orders").select("id", count="exact").eq("status", "pending").execute()
    pending_po = supabase.table("purchase_orders").select("id", count="exact").eq("status", "pending").execute()

    return {
        "total_products": total_items,
        "inventory_value": float(total_value),
        "pending_sales_orders": pending_so.count,
        "pending_purchase_orders": pending_po.count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
