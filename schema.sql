-- Core schema for Streamlit + Supabase ERP/POS
create extension if not exists "uuid-ossp";

-- Profiles + RBAC
create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    role text not null default 'cashier' check (role in ('admin', 'cashier')),
    created_at timestamptz not null default now()
);

-- Master data
create table if not exists catalog (
    item_id uuid primary key default uuid_generate_v4(),
    name text not null,
    type text not null,
    uom text not null,
    current_landed_cost numeric(14,2) not null default 0,
    default_sell_price numeric(14,2) not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists suppliers (
    supplier_id uuid primary key default uuid_generate_v4(),
    name text not null,
    phone text,
    created_at timestamptz not null default now()
);

-- Sales
create table if not exists sales_orders (
    order_id uuid primary key default uuid_generate_v4(),
    customer_name text not null,
    customer_phone text,
    total_amount numeric(14,2) not null default 0,
    deposit_paid numeric(14,2) not null default 0,
    balance_due numeric(14,2) not null default 0,
    status text not null default 'Pending' check (status in ('Pending', 'Completed', 'Cancelled')),
    created_at timestamptz not null default now()
);

create table if not exists order_lines (
    line_id uuid primary key default uuid_generate_v4(),
    order_id uuid not null references sales_orders(order_id) on delete cascade,
    item_id uuid not null references catalog(item_id),
    quantity numeric(14,3) not null,
    unit_price numeric(14,2) not null,
    line_total numeric(14,2) not null,
    line_cogs numeric(14,2) not null default 0,
    created_at timestamptz not null default now()
);

-- Inventory (immutable ledger)
create table if not exists inventory_ledger (
    ledger_id uuid primary key default uuid_generate_v4(),
    item_id uuid not null references catalog(item_id),
    transaction_type text not null check (transaction_type in ('INWARD', 'SALE', 'ADJUSTMENT')),
    quantity_change numeric(14,3) not null,
    unit_cost numeric(14,2),
    reason text,
    created_at timestamptz not null default now()
);

-- Purchasing + expenses
create table if not exists purchase_invoices (
    invoice_id uuid primary key default uuid_generate_v4(),
    item_id uuid not null references catalog(item_id),
    supplier_id uuid references suppliers(supplier_id),
    quantity numeric(14,3) not null,
    purchase_price numeric(14,2) not null,
    freight_cost numeric(14,2) not null default 0,
    landed_cost numeric(14,2) not null default 0,
    status text not null check (status in ('Paid', 'On Credit')),
    created_at timestamptz not null default now()
);

create table if not exists expenses (
    expense_id uuid primary key default uuid_generate_v4(),
    description text not null,
    amount numeric(14,2) not null,
    category text not null,
    expense_date timestamptz not null default now()
);

-- Audit log
create table if not exists audit_logs (
    log_id uuid primary key default uuid_generate_v4(),
    user_id uuid,
    action text not null check (action in ('UPDATE', 'DELETE')),
    table_name text not null,
    record_id text not null,
    old_value jsonb,
    new_value jsonb,
    timestamp timestamptz not null default now()
);

create index if not exists idx_inventory_ledger_item on inventory_ledger(item_id);
create index if not exists idx_order_lines_order on order_lines(order_id);
create index if not exists idx_purchase_invoices_item on purchase_invoices(item_id);
create index if not exists idx_audit_logs_time on audit_logs(timestamp desc);

-- ---------- RLS ----------
alter table profiles enable row level security;
alter table catalog enable row level security;
alter table suppliers enable row level security;
alter table sales_orders enable row level security;
alter table order_lines enable row level security;
alter table inventory_ledger enable row level security;
alter table purchase_invoices enable row level security;
alter table expenses enable row level security;
alter table audit_logs enable row level security;

-- helper function
create or replace function is_admin(uid uuid)
returns boolean
language sql
stable
as $$
    select exists(select 1 from profiles p where p.id = uid and p.role = 'admin');
$$;

-- read access for authenticated users
create policy if not exists read_all_catalog on catalog for select to authenticated using (true);
create policy if not exists read_all_suppliers on suppliers for select to authenticated using (true);
create policy if not exists read_all_sales_orders on sales_orders for select to authenticated using (true);
create policy if not exists read_all_order_lines on order_lines for select to authenticated using (true);
create policy if not exists read_all_inventory on inventory_ledger for select to authenticated using (true);
create policy if not exists read_all_purchase_invoices on purchase_invoices for select to authenticated using (true);
create policy if not exists read_all_expenses on expenses for select to authenticated using (true);
create policy if not exists read_own_profile on profiles for select to authenticated using (auth.uid() = id or is_admin(auth.uid()));
create policy if not exists read_audit_admin_only on audit_logs for select to authenticated using (is_admin(auth.uid()));

-- write policies
create policy if not exists insert_profiles_self on profiles for insert to authenticated with check (auth.uid() = id);
create policy if not exists update_profiles_admin on profiles for update to authenticated using (is_admin(auth.uid()));

create policy if not exists write_sales_orders_all on sales_orders for all to authenticated using (true) with check (true);
create policy if not exists write_order_lines_all on order_lines for all to authenticated using (true) with check (true);
create policy if not exists write_inventory_all on inventory_ledger for insert to authenticated with check (true);

create policy if not exists write_catalog_admin on catalog for all to authenticated using (is_admin(auth.uid())) with check (is_admin(auth.uid()));
create policy if not exists write_suppliers_admin on suppliers for all to authenticated using (is_admin(auth.uid())) with check (is_admin(auth.uid()));
create policy if not exists write_purchase_admin on purchase_invoices for all to authenticated using (is_admin(auth.uid())) with check (is_admin(auth.uid()));
create policy if not exists write_expenses_admin on expenses for all to authenticated using (is_admin(auth.uid())) with check (is_admin(auth.uid()));
create policy if not exists write_audit_all on audit_logs for insert to authenticated with check (true);
