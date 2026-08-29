import urllib.parse
import random
from datetime import datetime, timedelta
import urllib.parse
from faker import Faker
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

# 1. Database Connection Configuration
raw_password = "XXXX"
safe_password = urllib.parse.quote_plus(raw_password)
DB_URI = f"postgresql://postgres:{safe_password}@localhost:3696/inventory_db"
engine = create_engine(DB_URI)

print("Starting Enterprise Data Generation (Home Depot Model)...")

# ==========================================
# 1. SUPPLIERS (50 Global & Domestic Vendors)
# ==========================================
print("--> Generating 50 Suppliers...")
countries_lead_times = {
    "USA": (3, 10),
    "Canada": (5, 14),
    "Mexico": (7, 18),
    "Germany": (14, 28),
    "Japan": (18, 35),
    "China": (25, 45),
    "Vietnam": (28, 50)
}

suppliers_list = []
for i in range(1, 51):
    country = random.choice(list(countries_lead_times.keys()))
    min_lt, max_lt = countries_lead_times[country]
    suppliers_list.append({
        "supplier_id": f"SUP-{i:03d}",
        "supplier_name": f"{fake.company()} {random.choice(['Industrial', 'Supplies', 'Logistics', 'Manufacturing', 'Corp'])}",
        "country": country,
        "base_lead_time_days": random.randint(min_lt, max_lt),
        "reliability_score": round(random.uniform(0.75, 0.99), 2)
    })

df_suppliers = pd.DataFrame(suppliers_list)
df_suppliers.to_sql("suppliers", engine, if_exists="append", index=False)

# ==========================================
# 2. PRODUCTS (500 Home Depot SKUs)
# ==========================================
print("--> Generating 500 SKUs across Home Depot Categories...")
catalog_taxonomy = {
    "Lumber & Composites": {
        "items": ["2x4x8 Prime Framing Stud", "Plywood Sheathing 4x8", "Treated Deck Board 5/4x6", "Pressure Treated Post 4x4", "Cedar Shingle Bundle"],
        "cost_range": (8.0, 65.0)
    },
    "Power Tools": {
        "items": ["18V Brushless Drill Kit", "10-in Miter Saw", "Circular Saw 7-1/4in", "Reciprocating Saw Heavy Duty", "Rotary Hammer Drill SDS"],
        "cost_range": (80.0, 399.0)
    },
    "Hardware & Fasteners": {
        "items": ["3-in Deck Screws 5lb Box", "Galvanized Hex Bolt Pack", "Drywall Anchors Heavy Duty", "Framing Nails 21-Degree 1000ct", "Padlock Laminated Steel"],
        "cost_range": (6.0, 45.0)
    },
    "Plumbing": {
        "items": ["PEX-B Pipe 1/2in x 100ft", "Brass Ball Valve 3/4in", "Water Heater 40-Gal Natural Gas", "PVC Cleanout Plug 3in", "Submersible Sump Pump 1/2HP"],
        "cost_range": (12.0, 480.0)
    },
    "Electrical": {
        "items": ["12/2 NM-B Wire 250ft", "Single-Pole Smart Switch", "200A Main Breaker Panel", "1/2in EMT Conduit 10ft", "LED Shop Light 4ft 5000K"],
        "cost_range": (15.0, 220.0)
    },
    "Paint & Supplies": {
        "items": ["Interior Matte Paint 1-Gal", "Polyurethane Clear Gloss 1-Qt", "Microfiber Roller Cover 9in", "Painter Tape Pro 1.88in", "Airless Paint Sprayer"],
        "cost_range": (7.0, 260.0)
    }
}

products_list = []
sku_counter = 1001

for i in range(500):
    category = random.choice(list(catalog_taxonomy.keys()))
    base_item = random.choice(catalog_taxonomy[category]["items"])
    min_c, max_c = catalog_taxonomy[category]["cost_range"]
    
    cost = round(random.uniform(min_c, max_c), 2)
    # Retail markup between 35% and 85%
    markup = random.uniform(1.35, 1.85)
    price = round(cost * markup, 2)
    
    products_list.append({
        "sku": f"SKU-{sku_counter}",
        "product_name": f"{base_item} - {fake.word().capitalize()} Series",
        "category": category,
        "supplier_id": random.choice(df_suppliers["supplier_id"].tolist()),
        "unit_cost": cost,
        "unit_price": price
    })
    sku_counter += 1

df_products = pd.DataFrame(products_list)
df_products.to_sql("products", engine, if_exists="append", index=False)

# ==========================================
# 3. SALES TRANSACTIONS (~60,000+ Orders over 180 Days)
# ==========================================
print("--> Generating 180 Days of Historical Retail Demand with Weekend Velocity...")
end_date = datetime.today().date()
start_date = end_date - timedelta(days=180)
date_range = pd.date_range(start=start_date, end=end_date)

sales_orders = []
order_id = 100001

# Categorize product velocity (Fast movers vs. Slow movers)
product_skus = df_products[["sku", "unit_price", "category"]].to_dict("records")
for p in product_skus:
    # 20% Fast Movers (high daily volume), 60% Medium Movers, 20% Slow Movers (high ticket items)
    p["velocity_tier"] = np.random.choice(["fast", "medium", "slow"], p=[0.20, 0.60, 0.20])

for cur_date in date_range:
    is_weekend = cur_date.weekday() >= 5  # Saturday/Sunday demand spike at Home Depot
    multiplier = 1.45 if is_weekend else 1.0

    for prod in product_skus:
        # Probability of transaction on this date
        if prod["velocity_tier"] == "fast":
            prob = 0.85
            lam_val = 8 * multiplier
        elif prod["velocity_tier"] == "medium":
            prob = 0.50
            lam_val = 3 * multiplier
        else:
            prob = 0.20
            lam_val = 1 * multiplier

        if random.random() < prob:
            qty = max(1, int(np.random.poisson(lam=lam_val)))
            sales_orders.append({
                "order_id": f"ORD-{order_id}",
                "order_date": cur_date.date(),
                "sku": prod["sku"],
                "quantity_sold": qty,
                "total_amount": round(qty * prod["unit_price"], 2)
            })
            order_id += 1

df_sales = pd.DataFrame(sales_orders)
print(f"--> Ingesting {len(df_sales):,} Sales Orders into PostgreSQL in chunks...")
df_sales.to_sql("sales_orders", engine, if_exists="append", index=False, chunksize=10000)

# ==========================================
# 4. CURRENT INVENTORY LEVELS (500 Warehouse Records)
# ==========================================
print("--> Generating Current Warehouse Inventory Snapshots...")
inventory_list = []
zones = ["Aisle-A", "Aisle-B", "Aisle-C", "Aisle-D", "Yard-Bulk", "Bay-Racks"]

for prod in product_skus:
    # Intentionally distribute stock states: 15% Stockout Risk, 25% Near Reorder, 60% Healthy/Overstock
    status_bias = np.random.choice(["critical", "warning", "healthy"], p=[0.15, 0.25, 0.60])
    
    if status_bias == "critical":
        current_stock = random.randint(2, 25)
    elif status_bias == "warning":
        current_stock = random.randint(30, 95)
    else:
        current_stock = random.randint(150, 800)

    inventory_list.append({
        "sku": prod["sku"],
        "current_stock": current_stock,
        "safety_stock": 0,       # Will be computed dynamically via SQL
        "reorder_point": 0,      # Will be computed dynamically via SQL
        "warehouse_zone": random.choice(zones),
        "last_restock_date": end_date - timedelta(days=random.randint(2, 60))
    })

df_inventory = pd.DataFrame(inventory_list)
df_inventory.to_sql("inventory", engine, if_exists="append", index=False)

print(f"\nSUCCESS! Database Loaded with:")
print(f"- Suppliers: {len(df_suppliers):,} rows")
print(f"- Products: {len(df_products):,} rows")
print(f"- Sales Orders: {len(df_sales):,} rows")
print(f"- Inventory Snapshots: {len(df_inventory):,} rows")