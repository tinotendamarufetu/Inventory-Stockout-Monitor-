-- 1. Check Executive Risk Distribution
SELECT 
    stock_status,
    COUNT(*) AS total_skus,
    ROUND(SUM(total_inventory_value), 2) AS total_capital_tied_up,
    ROUND(AVG(days_inventory_remaining), 1) AS avg_days_remaining
FROM v_inventory_risk_monitor
GROUP BY stock_status
ORDER BY total_skus DESC;

-- 2. Preview the Top 10 Urgent SKUs Needing Immediate Replenishment
SELECT 
    sku,
    product_name,
    category,
    current_stock,
    reorder_point,
    days_inventory_remaining,
    recommended_order_qty,
    stock_status
FROM v_inventory_risk_monitor
WHERE stock_status = 'CRITICAL'
ORDER BY days_inventory_remaining ASC
LIMIT 10;