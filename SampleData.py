import snowflake.connector
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# ========================================
# 1️⃣ CONFIGURATION
# ========================================

SNOWFLAKE_CONFIG = {
    'user': 'SNOWFLAKE_INTERNAL_IT_ADMIN_USER',
    'password': 'qZYQ4xrni_TieD2',
    'account': 'WB19670-C2GPARTNERS',
    'warehouse': 'POWERHOUSE',
    'database': 'BLEND_INTERNAL_IT_APPS',
    'schema': 'RETRACE_BLENDX_DB'
}

# Simulation parameters
NUM_ITEMS = 50
NUM_WAREHOUSES = 5
SIMULATION_DAYS = 90
START_DATE = datetime(2024, 10, 1)

# Root cause distribution (deliberate failures)
FAILURE_TYPES = {
    'SUPPLIER_DELAY': 0.25,           # 25% of stockouts
    'FORECAST_UNDERESTIMATED': 0.20,  # 20%
    'THRESHOLD_TOO_LOW': 0.15,        # 15%
    'SAFETY_STOCK_INSUFFICIENT': 0.15, # 15%
    'STALE_FORECAST': 0.10,           # 10%
    'LEAD_TIME_WRONG': 0.10,          # 10%
    'NO_FAILURE': 0.05                # 5% (no stockout)
}

# ========================================
# 2️⃣ HELPER FUNCTIONS
# ========================================

def connect_snowflake():
    """Connect to Snowflake"""
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

def generate_item_id(i):
    return f"ITEM_{i:04d}"

def generate_warehouse_id(w):
    return f"WH_{w:02d}"

def generate_order_id(counter):
    return f"PO_{counter:06d}"

# ========================================
# 3️⃣ GENERATE BASE DATA
# ========================================

def generate_items_and_warehouses():
    """Create item-warehouse combinations"""
    combinations = []
    for item_idx in range(NUM_ITEMS):
        for wh_idx in range(NUM_WAREHOUSES):
            combinations.append({
                'item_id': generate_item_id(item_idx),
                'warehouse_id': generate_warehouse_id(wh_idx)
            })
    return combinations

# ========================================
# 4️⃣ GENERATE REORDER RULES
# ========================================

def generate_reorder_rules(combinations):
    """Create reorder rules with deliberate misconfigurations"""
    rules = []
    
    for combo in combinations:
        # Randomly assign failure scenario
        failure_scenario = np.random.choice(
            list(FAILURE_TYPES.keys()),
            p=list(FAILURE_TYPES.values())
        )
        
        # Base values (healthy defaults)
        base_safety_stock = random.randint(50, 100)
        base_lead_time = random.randint(5, 10)
        base_threshold = base_safety_stock + (20 * base_lead_time)
        
        # Introduce deliberate misconfigurations
        if failure_scenario == 'THRESHOLD_TOO_LOW':
            reorder_threshold = base_safety_stock + 10  # Too conservative
        elif failure_scenario == 'SAFETY_STOCK_INSUFFICIENT':
            base_safety_stock = random.randint(10, 30)  # Too small
            reorder_threshold = base_threshold
        else:
            reorder_threshold = base_threshold
        
        rules.append({
            'item_id': combo['item_id'],
            'safety_stock': base_safety_stock,
            'lead_time_days': base_lead_time,
            'reorder_threshold': reorder_threshold,
            'last_updated': START_DATE - timedelta(days=random.randint(30, 180)),
            'rule_owner': random.choice(['Alice', 'Bob', 'Charlie', 'Diana']),
            'failure_scenario': failure_scenario  # Track for later
        })
    
    return rules

# ========================================
# 5️⃣ GENERATE DEMAND FORECAST
# ========================================

def generate_demand_forecast(combinations, rules_map):
    """Create demand forecasts with realistic patterns"""
    forecasts = []
    
    for combo in combinations:
        item_id = combo['item_id']
        failure_scenario = rules_map[item_id]['failure_scenario']
        
        # Base daily demand
        base_demand = random.randint(10, 30)
        
        for day_offset in range(SIMULATION_DAYS):
            forecast_date = START_DATE + timedelta(days=day_offset)
            
            # Add variability
            demand_variance = random.randint(-5, 5)
            daily_demand = max(5, base_demand + demand_variance)
            
            # Introduce forecast errors based on scenario
            if failure_scenario == 'FORECAST_UNDERESTIMATED':
                # Forecast is 30% lower than reality
                forecasted_demand = int(daily_demand * 0.7)
                confidence = 0.6
                forecast_type = 'BASELINE'
            elif failure_scenario == 'STALE_FORECAST':
                # Forecast generated long ago
                generated_at = START_DATE - timedelta(days=60)
                forecasted_demand = daily_demand
                confidence = 0.4
                forecast_type = 'BASELINE'
            else:
                forecasted_demand = daily_demand
                generated_at = forecast_date - timedelta(days=1)
                confidence = random.uniform(0.7, 0.95)
                forecast_type = random.choice(['BASELINE', 'BASELINE', 'PROMO'])
            
            if failure_scenario != 'STALE_FORECAST':
                generated_at = forecast_date - timedelta(days=1)
            
            forecasts.append({
                'item_id': item_id,
                'forecast_date': forecast_date,
                'daily_demand': forecasted_demand,
                'generated_at': generated_at,
                'forecast_type': forecast_type,
                'forecast_confidence': confidence,
                'actual_demand': daily_demand  # Store for inventory calculation
            })
    
    return forecasts

# ========================================
# 6️⃣ GENERATE INVENTORY SNAPSHOTS
# ========================================

def generate_inventory_snapshots(combinations, rules_map, forecast_map):
    """Simulate daily inventory with realistic stock depletion"""
    snapshots = []
    inventory_state = {}  # Track current stock per item-warehouse
    
    # Initialize starting inventory
    for combo in combinations:
        key = (combo['item_id'], combo['warehouse_id'])
        inventory_state[key] = random.randint(300, 500)
    
    for day_offset in range(SIMULATION_DAYS):
        snapshot_date = START_DATE + timedelta(days=day_offset)
        
        for combo in combinations:
            item_id = combo['item_id']
            warehouse_id = combo['warehouse_id']
            key = (item_id, warehouse_id)
            
            # Get actual demand for this day
            forecast_key = (item_id, snapshot_date)
            actual_demand = forecast_map.get(forecast_key, {}).get('actual_demand', 15)
            
            # Reduce stock by demand
            inventory_state[key] = max(0, inventory_state[key] - actual_demand)
            
            # Determine if snapshot is stale
            is_stale = (day_offset > 60 and random.random() < 0.1)
            
            snapshots.append({
                'item_id': item_id,
                'warehouse_id': warehouse_id,
                'stock_on_hand': inventory_state[key],
                'snapshot_time': snapshot_date,
                'is_snapshot_stale': is_stale
            })
    
    return snapshots, inventory_state

# ========================================
# 7️⃣ GENERATE PURCHASE ORDERS
# ========================================

def generate_purchase_orders(combinations, rules_map, snapshots_list):
    """Create purchase orders with deliberate delays"""
    orders = []
    order_counter = 0
    
    # Group snapshots by item-warehouse
    snapshot_groups = {}
    for snap in snapshots_list:
        key = (snap['item_id'], snap['warehouse_id'])
        if key not in snapshot_groups:
            snapshot_groups[key] = []
        snapshot_groups[key].append(snap)
    
    for combo in combinations:
        item_id = combo['item_id']
        warehouse_id = combo['warehouse_id']
        key = (item_id, warehouse_id)
        
        rule = rules_map[item_id]
        failure_scenario = rule['failure_scenario']
        snapshots = snapshot_groups.get(key, [])
        
        for snap in snapshots:
            stock = snap['stock_on_hand']
            threshold = rule['reorder_threshold']
            
            # Check if reorder should trigger
            if stock <= threshold and stock > 0:
                order_id = generate_order_id(order_counter)
                order_counter += 1
                
                order_date = snap['snapshot_time']
                lead_time = rule['lead_time_days']
                expected_arrival = order_date + timedelta(days=lead_time)
                
                # Introduce delays based on scenario
                if failure_scenario == 'SUPPLIER_DELAY':
                    actual_delay = random.randint(5, 15)
                    actual_arrival = expected_arrival + timedelta(days=actual_delay)
                    status = 'DELAYED'
                    delay_reason = 'SUPPLIER_DELAY'
                elif failure_scenario == 'LEAD_TIME_WRONG':
                    actual_delay = random.randint(3, 8)
                    actual_arrival = expected_arrival + timedelta(days=actual_delay)
                    status = 'DELAYED'
                    delay_reason = 'LEAD_TIME_MISCONFIGURED'
                else:
                    actual_arrival = expected_arrival
                    status = 'RECEIVED'
                    delay_reason = None
                
                quantity = random.randint(100, 200)
                
                orders.append({
                    'order_id': order_id,
                    'item_id': item_id,
                    'order_date': order_date,
                    'expected_arrival_date': expected_arrival,
                    'actual_arrival_date': actual_arrival,
                    'quantity': quantity,
                    'status': status,
                    'delay_reason': delay_reason
                })
                
                # Only create one PO per threshold breach
                break
    
    return orders

# ========================================
# 8️⃣ GENERATE STOCKOUT EVENTS
# ========================================

def generate_stockout_events(combinations, rules_map, snapshots_list, orders_list):
    """Identify stockouts and assign root causes"""
    events = []
    
    # Group snapshots by item-warehouse
    snapshot_groups = {}
    for snap in snapshots_list:
        key = (snap['item_id'], snap['warehouse_id'])
        if key not in snapshot_groups:
            snapshot_groups[key] = []
        snapshot_groups[key].append(snap)
    
    # Group orders by item
    orders_by_item = {}
    for order in orders_list:
        item_id = order['item_id']
        if item_id not in orders_by_item:
            orders_by_item[item_id] = []
        orders_by_item[item_id].append(order)
    
    for combo in combinations:
        item_id = combo['item_id']
        warehouse_id = combo['warehouse_id']
        key = (item_id, warehouse_id)
        
        rule = rules_map[item_id]
        failure_scenario = rule['failure_scenario']
        snapshots = snapshot_groups.get(key, [])
        
        # Find stockout dates (stock = 0)
        for snap in snapshots:
            if snap['stock_on_hand'] == 0:
                stockout_date = snap['snapshot_time']
                
                # Check if reorder was triggered
                item_orders = orders_by_item.get(item_id, [])
                reorder_triggered = any(
                    order['order_date'] < stockout_date
                    for order in item_orders
                )
                
                # Determine failure category
                if reorder_triggered:
                    failure_category = 'EXECUTION_FAILURE'
                else:
                    failure_category = 'DECISION_FAILURE'
                
                # Assign root cause based on scenario
                root_cause = failure_scenario if failure_scenario != 'NO_FAILURE' else 'UNKNOWN'
                
                events.append({
                    'item_id': item_id,
                    'warehouse_id': warehouse_id,
                    'stockout_date': stockout_date,
                    'reorder_triggered': reorder_triggered,
                    'failure_category': failure_category,
                    'root_cause': root_cause,
                    'analysis_confidence': random.uniform(0.75, 0.95),
                    'analyzed_at': datetime.now()
                })
                
                # Only record first stockout
                break
    
    return events

# ========================================
# 9️⃣ MAIN EXECUTION
# ========================================

def main():
    print("🚀 Starting synthetic data generation...")
    
    # Step 1: Generate base entities
    print("📦 Generating items and warehouses...")
    combinations = generate_items_and_warehouses()
    print(f"   ✅ {len(combinations)} item-warehouse combinations")
    
    # Step 2: Generate reorder rules
    print("🛑 Generating reorder rules...")
    rules_list = generate_reorder_rules(combinations)
    rules_map = {r['item_id']: r for r in rules_list}
    print(f"   ✅ {len(rules_list)} rules created")
    
    # Step 3: Generate demand forecasts
    print("📈 Generating demand forecasts...")
    forecasts_list = generate_demand_forecast(combinations, rules_map)
    forecast_map = {(f['item_id'], f['forecast_date']): f for f in forecasts_list}
    print(f"   ✅ {len(forecasts_list)} forecasts created")
    
    # Step 4: Generate inventory snapshots
    print("📊 Generating inventory snapshots...")
    snapshots_list, _ = generate_inventory_snapshots(combinations, rules_map, forecast_map)
    print(f"   ✅ {len(snapshots_list)} snapshots created")
    
    # Step 5: Generate purchase orders
    print("🚚 Generating purchase orders...")
    orders_list = generate_purchase_orders(combinations, rules_map, snapshots_list)
    print(f"   ✅ {len(orders_list)} purchase orders created")
    
    # Step 6: Generate stockout events
    print("🚨 Generating stockout events...")
    events_list = generate_stockout_events(combinations, rules_map, snapshots_list, orders_list)
    print(f"   ✅ {len(events_list)} stockout events created")
    
    # Step 7: Insert into Snowflake
    print("\n💾 Inserting data into Snowflake...")
    conn = connect_snowflake()
    cursor = conn.cursor()
    # Export to CSV files
    pd.DataFrame(rules_list).to_csv('reorder_rules.csv', index=False)
    pd.DataFrame(forecasts_list).to_csv('demand_forecast.csv', index=False)
    pd.DataFrame(snapshots_list).to_csv('inventory_snapshot.csv', index=False)
    pd.DataFrame(orders_list).to_csv('purchase_orders.csv', index=False)
    pd.DataFrame(events_list).to_csv('stockout_events.csv', index=False)
    # try:
    #     # Insert Reorder Rules (exclude failure_scenario)
    #     print("   Inserting REORDER_RULES...")
    #     for rule in rules_list:
    #         cursor.execute("""
    #             INSERT INTO REORDER_RULES 
    #             (item_id, safety_stock, lead_time_days, reorder_threshold, last_updated, rule_owner)
    #             VALUES (%s, %s, %s, %s, %s, %s)
    #         """, (
    #             rule['item_id'],
    #             rule['safety_stock'],
    #             rule['lead_time_days'],
    #             rule['reorder_threshold'],
    #             rule['last_updated'],
    #             rule['rule_owner']
    #         ))
        
    #     # Insert Demand Forecasts
    #     print("   Inserting DEMAND_FORECAST...")
    #     for forecast in forecasts_list:
    #         cursor.execute("""
    #             INSERT INTO DEMAND_FORECAST
    #             (item_id, forecast_date, daily_demand, generated_at, forecast_type, forecast_confidence)
    #             VALUES (%s, %s, %s, %s, %s, %s)
    #         """, (
    #             forecast['item_id'],
    #             forecast['forecast_date'],
    #             forecast['daily_demand'],
    #             forecast['generated_at'],
    #             forecast['forecast_type'],
    #             forecast['forecast_confidence']
    #         ))
        
    #     # Insert Inventory Snapshots
    #     print("   Inserting INVENTORY_SNAPSHOT...")
    #     for snap in snapshots_list:
    #         cursor.execute("""
    #             INSERT INTO INVENTORY_SNAPSHOT
    #             (item_id, warehouse_id, stock_on_hand, snapshot_time, is_snapshot_stale)
    #             VALUES (%s, %s, %s, %s, %s)
    #         """, (
    #             snap['item_id'],
    #             snap['warehouse_id'],
    #             snap['stock_on_hand'],
    #             snap['snapshot_time'],
    #             snap['is_snapshot_stale']
    #         ))
        
    #     # Insert Purchase Orders
    #     print("   Inserting PURCHASE_ORDERS...")
    #     for order in orders_list:
    #         cursor.execute("""
    #             INSERT INTO PURCHASE_ORDERS
    #             (order_id, item_id, order_date, expected_arrival_date, actual_arrival_date, quantity, status, delay_reason)
    #             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    #         """, (
    #             order['order_id'],
    #             order['item_id'],
    #             order['order_date'],
    #             order['expected_arrival_date'],
    #             order['actual_arrival_date'],
    #             order['quantity'],
    #             order['status'],
    #             order['delay_reason']
    #         ))
        
    #     # Insert Stockout Events
    #     print("   Inserting STOCKOUT_EVENTS...")
    #     for event in events_list:
    #         cursor.execute("""
    #             INSERT INTO STOCKOUT_EVENTS
    #             (item_id, warehouse_id, stockout_date, reorder_triggered, failure_category, root_cause, analysis_confidence, analyzed_at)
    #             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    #         """, (
    #             event['item_id'],
    #             event['warehouse_id'],
    #             event['stockout_date'],
    #             event['reorder_triggered'],
    #             event['failure_category'],
    #             event['root_cause'],
    #             event['analysis_confidence'],
    #             event['analyzed_at']
    #         ))
        
    #     conn.commit()
    #     print("\n✅ All data inserted successfully!")
        
    # except Exception as e:
    #     print(f"\n❌ Error: {e}")
    #     conn.rollback()
    
    # finally:
    #     cursor.close()
    #     conn.close()
    
    # Print summary
    print("\n" + "="*50)
    print("📊 DATA GENERATION SUMMARY")
    print("="*50)
    print(f"Items: {NUM_ITEMS}")
    print(f"Warehouses: {NUM_WAREHOUSES}")
    print(f"Simulation Days: {SIMULATION_DAYS}")
    print(f"Reorder Rules: {len(rules_list)}")
    print(f"Demand Forecasts: {len(forecasts_list)}")
    print(f"Inventory Snapshots: {len(snapshots_list)}")
    print(f"Purchase Orders: {len(orders_list)}")
    print(f"Stockout Events: {len(events_list)}")
    print("="*50)

if __name__ == "__main__":
    main()