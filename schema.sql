-- Curtain Shop ERP Database Schema for Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Products table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    unit_of_measure VARCHAR(50) DEFAULT 'piece',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Customers table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Suppliers table
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inventory ledger (tracks all stock movements)
CREATE TABLE inventory_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50) NOT NULL, -- 'purchase', 'sale', 'adjustment', 'return'
    quantity DECIMAL(12, 3) NOT NULL, -- positive for in, negative for out
    unit_cost DECIMAL(12, 2), -- cost per unit at time of transaction
    total_cost DECIMAL(12, 2), -- quantity * unit_cost
    reference_id UUID, -- order_id or adjustment_id
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sales orders table
CREATE TABLE sales_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID REFERENCES customers(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, confirmed, completed, cancelled
    order_date DATE DEFAULT CURRENT_DATE,
    delivery_date DATE,
    subtotal DECIMAL(12, 2) DEFAULT 0,
    tax_amount DECIMAL(12, 2) DEFAULT 0,
    discount_amount DECIMAL(12, 2) DEFAULT 0,
    total_amount DECIMAL(12, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sales order items
CREATE TABLE sales_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity DECIMAL(12, 3) NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    line_total DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Purchase orders table
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id UUID REFERENCES suppliers(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, received, cancelled
    order_date DATE DEFAULT CURRENT_DATE,
    expected_date DATE,
    subtotal DECIMAL(12, 2) DEFAULT 0,
    shipping_cost DECIMAL(12, 2) DEFAULT 0,
    other_costs DECIMAL(12, 2) DEFAULT 0,
    total_landed_cost DECIMAL(12, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Purchase order items
CREATE TABLE purchase_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity DECIMAL(12, 3) NOT NULL,
    unit_cost DECIMAL(12, 2) NOT NULL,
    line_total DECIMAL(12, 2) NOT NULL,
    allocated_landed_cost DECIMAL(12, 2) DEFAULT 0,
    final_unit_cost DECIMAL(12, 2), -- includes landed cost allocation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Current inventory view (auto-calculated from ledger)
CREATE OR REPLACE VIEW current_inventory AS
SELECT 
    p.id AS product_id,
    p.sku,
    p.name,
    p.category,
    COALESCE(SUM(il.quantity), 0) AS quantity_on_hand,
    COALESCE(AVG(il.unit_cost), 0) AS average_cost,
    COALESCE(SUM(il.quantity), 0) * COALESCE(AVG(il.unit_cost), 0) AS inventory_value
FROM products p
LEFT JOIN inventory_ledger il ON p.id = il.product_id
GROUP BY p.id, p.sku, p.name, p.category;

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_suppliers_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sales_orders_updated_at
    BEFORE UPDATE ON sales_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_purchase_orders_updated_at
    BEFORE UPDATE ON purchase_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes for performance
CREATE INDEX idx_inventory_ledger_product ON inventory_ledger(product_id);
CREATE INDEX idx_inventory_ledger_created ON inventory_ledger(created_at);
CREATE INDEX idx_sales_orders_customer ON sales_orders(customer_id);
CREATE INDEX idx_sales_orders_status ON sales_orders(status);
CREATE INDEX idx_sales_order_items_order ON sales_order_items(order_id);
CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_order_items_order ON purchase_order_items(order_id);

-- Sample data (optional - remove in production)
INSERT INTO products (sku, name, category, unit_of_measure) VALUES
    ('CURT-001', 'Velvet Curtain Panel - Navy', 'Curtains', 'piece'),
    ('CURT-002', 'Linen Curtain Panel - Beige', 'Curtains', 'piece'),
    ('ROD-001', 'Metal Curtain Rod - Silver', 'Hardware', 'piece'),
    ('ROD-002', 'Wooden Curtain Rod - Oak', 'Hardware', 'piece'),
    ('ACC-001', 'Curtain Tieback Set', 'Accessories', 'set');

INSERT INTO customers (name, email, phone) VALUES
    ('Walk-in Customer', 'walkin@example.com', 'N/A'),
    ('John Smith', 'john.smith@email.com', '+1-555-0101'),
    ('Sarah Johnson', 'sarah.j@email.com', '+1-555-0102');

INSERT INTO suppliers (name, contact_person, email, phone) VALUES
    ('Fabric World Inc.', 'Mike Chen', 'sales@fabricworld.com', '+1-555-0201'),
    ('Home Decor Wholesale', 'Lisa Park', 'orders@homedecorws.com', '+1-555-0202');
