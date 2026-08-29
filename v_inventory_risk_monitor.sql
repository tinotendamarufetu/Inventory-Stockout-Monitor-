-- 1. Drop existing view schema
DROP VIEW IF EXISTS v_inventory_risk_monitor;

-- 2. Recreate with all columns including restock dates
CREATE OR REPLACE VIEW v_inventory_risk_monitor AS
WITH daily_sales_agg AS (
    -- Step 1: Aggregate sales per SKU per day
    SELECT 
        sku,
        order_date,
        SUM(quantity_sold) AS daily_units_sold
    FROM sales_orders
    GROUP BY sku, order_date
),
demand_metrics AS (
    -- Step 2: Compute average and peak daily demand per SKU
    SELECT 
        sku,
        ROUND(AVG(daily_units_sold), 2) AS avg_daily_demand,
        MAX(daily_units_sold) AS max_daily_demand,
        COUNT(DISTINCT order_date) AS active_sales_days
    FROM daily_sales_agg
    GROUP BY sku
),
sku_supply_profile AS (
    -- Step 3: Join products, suppliers, and inventory
    SELECT 
        p.sku,
        p.product_name,
        p.category,
        p.unit_cost,
        p.unit_price,
        s.supplier_name,
        s.country AS supplier_country,
        s.base_lead_time_days AS avg_lead_time,
        ROUND(s.base_lead_time_days * (1 + (1 - s.reliability_score)), 0)::INT AS max_lead_time,
        s.reliability_score,
        i.current_stock,
        i.warehouse_zone,
        i.last_restock_date,
        COALESCE(dm.avg_daily_demand, 0.1) AS avg_daily_demand,
        COALESCE(dm.max_daily_demand, 1) AS max_daily_demand
    FROM products p
    JOIN suppliers s ON p.supplier_id = s.supplier_id
    JOIN inventory i ON p.sku = i.sku
    LEFT JOIN demand_metrics dm ON p.sku = dm.sku
),
inventory_calculations AS (
    -- Step 4: Apply Safety Stock, ROP, DIR, and Capital metrics
    SELECT 
        sku,
        product_name,
        category,
        supplier_name,
        supplier_country,
        warehouse_zone,
        last_restock_date,
        (CURRENT_DATE - last_restock_date) AS days_since_last_restock,
        unit_cost,
        unit_price,
        current_stock,
        avg_daily_demand,
        max_daily_demand,
        avg_lead_time,
        max_lead_time,
        reliability_score,
        -- Safety Stock = (Max Demand * Max Lead Time) - (Avg Demand * Avg Lead Time)
        GREATEST(
            0,
            ROUND((max_daily_demand * max_lead_time) - (avg_daily_demand * avg_lead_time), 0)
        )::INT AS safety_stock,
        -- Reorder Point = (Avg Demand * Avg Lead Time) + Safety Stock
        ROUND(
            (avg_daily_demand * avg_lead_time) + 
            GREATEST(0, (max_daily_demand * max_lead_time) - (avg_daily_demand * avg_lead_time)), 
            0
        )::INT AS reorder_point,
        -- Days of Inventory Remaining (DIR)
        ROUND(current_stock / NULLIF(avg_daily_demand, 0), 1) AS days_inventory_remaining,
        -- Total Capital Tied Up ($)
        ROUND(current_stock * unit_cost, 2) AS total_inventory_value
    FROM sku_supply_profile
)
-- Step 5: Risk Classification
SELECT 
    *,
    CASE 
        WHEN current_stock <= reorder_point OR days_inventory_remaining <= 7.0 THEN 'CRITICAL'
        WHEN current_stock <= (reorder_point * 1.25) OR days_inventory_remaining <= 14.0 THEN 'WARNING'
        WHEN days_inventory_remaining > 60.0 THEN 'OVERSTOCKED'
        ELSE 'HEALTHY'
    END AS stock_status,
    CASE 
        WHEN current_stock <= reorder_point THEN GREATEST(reorder_point * 2 - current_stock, 50)
        ELSE 0
    END AS recommended_order_qty
FROM inventory_calculations;