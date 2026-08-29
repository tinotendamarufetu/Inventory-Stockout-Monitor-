from datetime import datetime
import os
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine

# 1. Database Connection
raw_password = "XXXX"
safe_password = urllib.parse.quote_plus(raw_password)
DB_URI = f"postgresql://postgres:{safe_password}@localhost:3696/inventory_db"
engine = create_engine(DB_URI)

def run_procurement_dispatch():
    print("=" * 70)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RUNNING DAILY REPLENISHMENT SCAN")
    print("=" * 70)

    # 2. Extract actionable SKUs from our analytical SQL view
    query = """
        SELECT 
            sku,
            product_name,
            category,
            supplier_name,
            supplier_country,
            warehouse_zone,
            current_stock,
            reorder_point,
            days_inventory_remaining,
            recommended_order_qty,
            unit_cost,
            ROUND(recommended_order_qty * unit_cost, 2) AS estimated_po_cost,
            stock_status
        FROM v_inventory_risk_monitor
        WHERE stock_status IN ('CRITICAL', 'WARNING')
        ORDER BY days_inventory_remaining ASC, estimated_po_cost DESC;
    """
    
    df_alerts = pd.read_sql(query, engine)
    
    if df_alerts.empty:
        print("All SKUs are healthy. No replenishment orders needed.")
        return

    # 3. Compute Executive Summary Metrics
    critical_count = len(df_alerts[df_alerts["stock_status"] == "CRITICAL"])
    warning_count = len(df_alerts[df_alerts["stock_status"] == "WARNING"])
    total_budget_required = df_alerts["estimated_po_cost"].sum()
    unique_vendors = df_alerts["supplier_name"].nunique()

    print(f"\nEXECUTIVE SCAN SUMMARY:")
    print(f" • Critical Stockout SKUs : {critical_count}")
    print(f" • Warning Threshold SKUs : {warning_count}")
    print(f" • Impacted Suppliers     : {unique_vendors}")
    print(f" • Total PO Budget Needed : ${total_budget_required:,.2f}")

    # 4. Generate Output Directory & Timestamped PO Manifest
    os.makedirs("dispatch_orders", exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"dispatch_orders/PO_Manifest_{timestamp_str}.csv"
    
    df_alerts.to_csv(file_path, index=False)
    print(f"\nAutomated PO Manifest Exported: {file_path}")
    print("Ready for automated email dispatch to Procurement Team.\n")

if __name__ == "__main__":
    run_procurement_dispatch()