import snowflake.connector
from src.utils.config import SF_USER, SF_PASSWORD, SF_ACCOUNT, SF_WAREHOUSE, SF_DATABASE, SF_SCHEMA
from typing import Union
import os
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text



import requests
from fastapi import APIRouter, Depends, HTTPException


# def get_events(db: Session):
#     query = text("""
#         SELECT * FROM STOCKOUT_EVENTS
#         ORDER BY stockout_date DESC;
#     """)
#     result = db.execute(query)
#     rows = result.fetchall()
#     return [dict(row._mapping) for row in rows]


def get_events(
    db: Session,
    limit: int = 100,
    failure_category: Optional[str] = None,
    root_cause: Optional[str] = None
):
    params: Dict[str, Any] = {"limit": limit}
    filters = []

    if failure_category:
        filters.append("failure_category = :failure_category")
        params["failure_category"] = failure_category

    if root_cause:
        filters.append("root_cause = :root_cause")
        params["root_cause"] = root_cause

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = text(f"""
        SELECT *
        FROM STOCKOUT_EVENTS
        {where_clause}
        ORDER BY stockout_date DESC
        LIMIT :limit
    """)

    result = db.execute(query, params)
    return [dict(row._mapping) for row in result.fetchall()]
    
def get_event_details(db: Session, item_id: str):
    item_id = item_id.upper()

    query = text("""
        WITH ev AS (
            SELECT *
            FROM STOCKOUT_EVENTS
            WHERE item_id = :item_id
            ORDER BY stockout_date DESC
            LIMIT 1
        ),
        inv AS (
            SELECT stock_on_hand
            FROM INVENTORY_SNAPSHOT
            WHERE item_id = :item_id
              AND warehouse_id = (SELECT warehouse_id FROM ev)
              AND snapshot_time <= (SELECT stockout_date FROM ev)
            ORDER BY snapshot_time DESC
            LIMIT 1
        ),
        fc AS (
            SELECT daily_demand
            FROM DEMAND_FORECAST
            WHERE item_id = :item_id
              AND forecast_created_date <= (SELECT stockout_date FROM ev)
            ORDER BY forecast_created_date DESC
            LIMIT 1
        ),
        rules AS (
            SELECT *
            FROM REORDER_RULES
            WHERE item_id = :item_id
        ),
        incoming AS (
            SELECT COALESCE(SUM(quantity), 0) AS incoming_qty
            FROM PURCHASE_ORDERS
            WHERE item_id = :item_id
              AND expected_arrival_date > (SELECT stockout_date FROM ev)
        )
        SELECT
            inv.stock_on_hand,
            incoming.incoming_qty,
            fc.daily_demand,
            rules.safety_stock,
            rules.lead_time_days,
            (fc.daily_demand * rules.lead_time_days + rules.safety_stock) AS reorder_need_threshold,
            (inv.stock_on_hand + incoming.incoming_qty) AS projected_stock,
            CASE
              WHEN (inv.stock_on_hand + incoming.incoming_qty)
                   <= (fc.daily_demand * rules.lead_time_days + rules.safety_stock)
              THEN 'REORDER SHOULD HAVE TRIGGERED'
              ELSE 'NO REORDER EXPECTED'
            END AS explanation
        FROM inv, fc, rules, incoming;
    """)

    result = db.execute(query, {"item_id": item_id})
    row = result.fetchone()
    return dict(row._mapping) if row else {}

def simulate_event(db: Session, item_id: str):
    item_id = item_id.upper()

    query = text("""
        WITH rules AS (
            SELECT *
            FROM REORDER_RULES
            WHERE item_id = :item_id
        ),
        fc AS (
            SELECT daily_demand
            FROM DEMAND_FORECAST
            WHERE item_id = :item_id
            ORDER BY forecast_created_date DESC
            LIMIT 1
        ),
        inv AS (
            SELECT stock_on_hand
            FROM INVENTORY_SNAPSHOT
            WHERE item_id = :item_id
            ORDER BY snapshot_time DESC
            LIMIT 1
        ),
        incoming AS (
            SELECT COALESCE(SUM(quantity), 0) AS incoming_qty
            FROM PURCHASE_ORDERS
            WHERE item_id = :item_id
        )
        SELECT
            rules.safety_stock + 5 AS new_safety_stock,
            (fc.daily_demand * rules.lead_time_days + (rules.safety_stock + 5)) AS new_threshold,
            (inv.stock_on_hand + incoming.incoming_qty) AS projected_stock_after_fix,
            CASE
              WHEN (inv.stock_on_hand + incoming.incoming_qty)
                   <= (fc.daily_demand * rules.lead_time_days + (rules.safety_stock + 5))
              THEN 'STILL FAILS'
              ELSE 'PREVENTS STOCKOUT'
            END AS outcome
        FROM inv, fc, rules, incoming;
    """)

    result = db.execute(query, {"item_id": item_id})
    row = result.fetchone()
    return dict(row._mapping) if row else {}


def save_user_info(db, user):
    """Save or update user info in database"""
    from sqlalchemy import text
    from src.utils.config import RETRACE_USER
    
    sql = text(f"""
        MERGE INTO {RETRACE_USER} AS target
        USING (
            SELECT 
                :id AS ID, 
                :name AS NAME, 
                :email AS EMAIL, 
                :roles AS ROLES
        ) AS source
        ON target.EMAIL = source.EMAIL
        WHEN MATCHED THEN
            UPDATE 
            SET NAME = source.NAME,
                ROLES = source.ROLES,
                IS_ACTIVE = TRUE
        WHEN NOT MATCHED THEN
            INSERT (ID, NAME, EMAIL, ROLES, IS_ACTIVE)
            VALUES (source.ID, source.NAME, source.EMAIL, source.ROLES, TRUE);
    """)

    
    db.execute(sql, {'id': user.id, 'name': user.name, 'email': user.email, 'roles': user.roles or 'GENERAL'})
    db.commit()












def get_dashboard_summary(db: Session, days: int = 30):
    """High-level metrics for dashboard"""
    query = text(f"""
        WITH recent_events AS (
            SELECT * FROM STOCKOUT_EVENTS
            WHERE stockout_date >= DATEADD(day, -{days}, CURRENT_DATE())
        )
        SELECT 
            COUNT(*) AS total_stockouts,
            SUM(CASE WHEN failure_category = 'EXECUTION_FAILURE' THEN 1 ELSE 0 END) AS execution_failures,
            SUM(CASE WHEN failure_category = 'DECISION_FAILURE' THEN 1 ELSE 0 END) AS decision_failures,
            AVG(analysis_confidence) AS avg_confidence,
            (SELECT root_cause FROM recent_events GROUP BY root_cause ORDER BY COUNT(*) DESC LIMIT 1) AS top_root_cause
        FROM recent_events;
    """)
    result = db.execute(query)
    row = result.fetchone()
    return dict(row._mapping) if row else {}


def get_root_cause_distribution(db: Session):
    """Root cause breakdown for charts"""
    query = text("""
        SELECT 
            root_cause,
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
        FROM STOCKOUT_EVENTS
        GROUP BY root_cause
        ORDER BY count DESC;
    """)
    result = db.execute(query)
    return [dict(row._mapping) for row in result.fetchall()]


# def get_inventory_timeline(db: Session, item_id: str, days: int = 30):
#     """Stock level history with annotations"""
#     item_id = item_id.upper()
#     query = text(f"""
#         SELECT 
#             i.snapshot_time,
#             i.stock_on_hand,
#             r.reorder_threshold,
#             r.safety_stock,
#             CASE 
#                 WHEN i.stock_on_hand <= r.reorder_threshold THEN 'BELOW_THRESHOLD'
#                 WHEN i.stock_on_hand <= r.safety_stock THEN 'CRITICAL'
#                 ELSE 'HEALTHY'
#             END AS status
#         FROM INVENTORY_SNAPSHOT i
#         JOIN REORDER_RULES r ON i.item_id = r.item_id
#         WHERE i.item_id = :item_id
#           AND i.snapshot_time >= DATEADD(day, -{days}, CURRENT_DATE())
#         ORDER BY i.snapshot_time;
#     """)
#     result = db.execute(query, {'item_id': item_id})
#     return [dict(row._mapping) for row in result.fetchall()]

def get_inventory_timeline(db: Session, item_id: str, days: int = 30):
    item_id = item_id.upper()

    query = text("""
        WITH latest AS (
            SELECT MAX(snapshot_time) AS max_time
            FROM INVENTORY_SNAPSHOT
            WHERE item_id = :item_id
        )
        SELECT 
            i.snapshot_time,
            i.stock_on_hand,
            r.reorder_threshold,
            r.safety_stock,
            CASE 
                WHEN i.stock_on_hand <= r.reorder_threshold THEN 'BELOW_THRESHOLD'
                WHEN i.stock_on_hand <= r.safety_stock THEN 'CRITICAL'
                ELSE 'HEALTHY'
            END AS status
        FROM INVENTORY_SNAPSHOT i
        JOIN REORDER_RULES r 
          ON i.item_id = r.item_id
        JOIN latest l
          ON i.snapshot_time >= DATEADD(day, -:days, l.max_time)
        WHERE i.item_id = :item_id
        ORDER BY i.snapshot_time;
    """)

    result = db.execute(query, {
        "item_id": item_id,
        "days": days
    })

    return [dict(row._mapping) for row in result.fetchall()]


def get_forecast_accuracy(db: Session, item_id: str):
    """Compare forecast vs reality"""
    item_id = item_id.upper()
    query = text("""
        SELECT 
            forecast_date,
            daily_demand AS forecasted,
            forecast_confidence,
            -- Note: In real system, you'd join with actual sales data
            -- For now, we show forecast variance
            CASE 
                WHEN forecast_confidence < 0.6 THEN 'LOW_CONFIDENCE'
                WHEN forecast_confidence < 0.8 THEN 'MEDIUM_CONFIDENCE'
                ELSE 'HIGH_CONFIDENCE'
            END AS confidence_level
        FROM DEMAND_FORECAST
        WHERE item_id = :item_id
        ORDER BY forecast_date DESC
        LIMIT 30;
    """)
    result = db.execute(query, {'item_id': item_id})
    return [dict(row._mapping) for row in result.fetchall()]


def get_supplier_performance(db: Session):
    """Supplier delay analysis"""
    query = text("""
        SELECT 
            delay_reason,
            COUNT(*) AS total_delays,
            AVG(DATEDIFF(day, expected_arrival_date, actual_arrival_date)) AS avg_delay_days,
            SUM(CASE WHEN status = 'DELAYED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS delay_rate_pct
        FROM PURCHASE_ORDERS
        WHERE delay_reason IS NOT NULL
        GROUP BY delay_reason
        ORDER BY total_delays DESC;
    """)
    result = db.execute(query)
    return [dict(row._mapping) for row in result.fetchall()]


def get_similar_failures(db: Session, item_id: str, limit: int = 5):
    """Find similar failure patterns"""
    item_id = item_id.upper()
    query = text("""
        WITH target_event AS (
            SELECT root_cause, failure_category, warehouse_id
            FROM STOCKOUT_EVENTS
            WHERE item_id = :item_id
            LIMIT 1
        )
        SELECT 
            s.item_id,
            s.stockout_date,
            s.root_cause,
            s.failure_category
        FROM STOCKOUT_EVENTS s, target_event t
        WHERE s.item_id != :item_id
          AND s.root_cause = t.root_cause
          AND s.failure_category = t.failure_category
        ORDER BY s.stockout_date DESC
        LIMIT :limit;
    """)
    result = db.execute(query, {'item_id': item_id, 'limit': limit})
    return [dict(row._mapping) for row in result.fetchall()]


def analyze_stockout_with_ai(db: Session, item_id: str):
    """Use Cortex AI to explain failure in natural language"""
    item_id = item_id.upper()
    
    # Get event data
    event_query = text("""
        SELECT * FROM STOCKOUT_EVENTS
        WHERE item_id = :item_id
        ORDER BY stockout_date DESC
        LIMIT 1;
    """)
    event = db.execute(event_query, {'item_id': item_id}).fetchone()
    
    if not event:
        return {"error": "No stockout found for this item"}
    
    # Build context for AI
    prompt = f"""
    Explain this stockout in 2-3 sentences for a supply chain manager:
    
    Item: {event.item_id}
    Date: {event.stockout_date}
    Failure Type: {event.failure_category}
    Root Cause: {event.root_cause}
    Reorder Triggered: {event.reorder_triggered}
    
    Be specific and actionable.
    """
    
    # Call Cortex
    ctx = db.connection().connection
    cs = ctx.cursor()
    try:
        cs.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large', %s)",
            (prompt,)
        )
        row = cs.fetchone()
        return {
            "item_id": item_id,
            "ai_explanation": row[0] if row else "Analysis unavailable"
        }
    finally:
        cs.close()
        ctx.close()


def get_reorder_triggers(
    db: Session,
    item_id: Optional[str] = None,
    days: int = 30
):
    filters = []
    params: Dict[str, Any] = {"days": days}

    if item_id:
        filters.append("item_id = :item_id")
        params["item_id"] = item_id.upper()

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = text(f"""
        SELECT 
            order_id,
            item_id,
            order_date AS trigger_date,
            'REORDER_TRIGGERED' AS event_type,
            status
        FROM PURCHASE_ORDERS
        {where_clause}
        {"AND" if where_clause else "WHERE"}
        order_date >= DATEADD(day, -:days, CURRENT_DATE())
        ORDER BY order_date DESC
    """)

    result = db.execute(query, params)
    return [dict(row._mapping) for row in result.fetchall()]

# def get_reorder_triggers(db: Session, item_id: str = None, days: int = 30):
#     """Show reorder trigger history (placeholder - requires REORDER_TRIGGERS table)"""
#     # If you added REORDER_TRIGGERS table, implement this
#     # For now, we can infer from purchase orders
#     filters = []
#     params = {'days': days}
    
#     if item_id:
#         filters.append("item_id = :item_id")
#         params['item_id'] = item_id.upper()
    
#     where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
#     query = text(f"""
#         SELECT 
#             order_id,
#             item_id,
#             order_date AS trigger_date,
#             'REORDER_TRIGGERED' AS event_type,
#             status
#         FROM PURCHASE_ORDERS
#         {where_clause}
#           AND order_date >= DATEADD(day, -{days}, CURRENT_DATE())
#         ORDER BY order_date DESC;
#     """)
    
#     result = db.execute(query, params)
#     return [dict(row._mapping) for row in result.fetchall()]


















def update_user_role(db, email: str, role: str):
    """Update user role"""
    from sqlalchemy import text
    from src.utils.config import RETRACE_USER
    
    sql = text(f"UPDATE {RETRACE_USER} SET ROLES = :role WHERE EMAIL = :email")
    result = db.execute(sql, {'email': email, 'role': role})
    
    if result.rowcount == 0:
        raise ValueError(f"User with email {email} not found")
    
    db.commit()
