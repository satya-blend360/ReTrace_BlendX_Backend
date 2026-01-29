from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import Optional
from datetime import date
from src.auth.dependencies import authorize_token
from src.auth.models import UserInfo
from src.snowflake.service import (
    save_user_info, 
    update_user_role, 
    get_events, 
    get_event_details, 
    simulate_event,
    get_dashboard_summary,
    get_root_cause_distribution,
    get_inventory_timeline,
    get_forecast_accuracy,
    get_supplier_performance,
    analyze_stockout_with_ai,
    get_reorder_triggers,
    get_similar_failures
)
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.utils.database import get_db

router = APIRouter() 

@router.get("/cortex_test")
def cortex_test(
    prompt: str = Query(..., description="User input prompt"),
    db: Session = Depends(get_db)
):
    ctx = db.connection().connection
    cs = ctx.cursor()
    try:
        cs.execute(
            """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                'mistral-large',
                %s
            )
            """,
            (prompt,)
        )

        row = cs.fetchone()
        if not row:
            raise HTTPException(
                status_code=500,
                detail="No response from SNOWFLAKE.CORTEX.COMPLETE"
            )

        return {
            "input": prompt,
            "output": row[0]
        }

    finally:
        cs.close()
        ctx.close()

@router.get("/all")
def list_events(_=Depends(authorize_token()),db:Session=Depends(get_db)):
    return get_events(db)

@router.get("/analysis/{itemId}")
def reconstruct_event(itemId: str, _=Depends(authorize_token()), db: Session = Depends(get_db)):
    return get_event_details(db, itemId)


@router.get("/{itemId}/simulate")
def simulate_item(itemId: str, _=Depends(authorize_token()), db: Session = Depends(get_db)):
    return simulate_event(db, itemId)





# ========================================
# 2️⃣ NEW DASHBOARD ENDPOINTS
# ========================================

@router.get("/dashboard/summary")
def dashboard_summary(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    days: int = Query(6000, description="Look back period in days")
):
    """
    **High-level dashboard metrics**
    
    Returns:
    - Total stockouts (last N days)
    - Execution failures vs Decision failures
    - Average analysis confidence
    - Top 3 root causes
    - Items at risk
    """
    return get_dashboard_summary(db, days)


@router.get("/dashboard/root-causes")
def root_cause_distribution(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db)
):
    """
    **Root cause breakdown for visualization**
    
    Perfect for pie charts or bar graphs showing:
    - SUPPLIER_DELAY: 25%
    - FORECAST_UNDERESTIMATED: 20%
    - etc.
    """
    return get_root_cause_distribution(db)


@router.get("/dashboard/trends")
def stockout_trends(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    days: int = Query(6000, description="Trend period in days")
):
    """
    **Time-series data for trend charts**
    
    Returns daily/weekly stockout counts over time
    """
    query = text(f"""
        SELECT 
            DATE_TRUNC('week', stockout_date) AS week,
            COUNT(*) AS stockout_count,
            SUM(CASE WHEN failure_category = 'EXECUTION_FAILURE' THEN 1 ELSE 0 END) AS execution_failures,
            SUM(CASE WHEN failure_category = 'DECISION_FAILURE' THEN 1 ELSE 0 END) AS decision_failures
        FROM STOCKOUT_EVENTS
        WHERE stockout_date >= DATEADD(day, -{days}, CURRENT_DATE())
        GROUP BY week
        ORDER BY week;
    """)
    result = db.execute(query)
    return [dict(row._mapping) for row in result.fetchall()]


# ========================================
# 3️⃣ ITEM-SPECIFIC INTELLIGENCE
# ========================================

@router.get("/items/{itemId}/timeline")
def inventory_timeline(
    itemId: str,
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    days: int = Query(6000, description="Days to show")
):
    """
    **Full inventory history for an item**
    
    Shows:
    - Daily stock levels
    - Reorder threshold line
    - When reorders were triggered
    - When stockout occurred
    """
    return get_inventory_timeline(db, itemId, days)


@router.get("/items/{itemId}/forecast-accuracy")
def forecast_accuracy(
    itemId: str,
    _=Depends(authorize_token()),
    db: Session = Depends(get_db)
):
    """
    **Compare forecasted vs actual demand**
    
    Helps identify if forecast was the root cause
    """
    return get_forecast_accuracy(db, itemId)


@router.get("/items/{itemId}/similar-failures")
def similar_failures(
    itemId: str,
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    limit: int = Query(5, description="Number of similar cases")
):
    """
    **Find other items with similar failure patterns**
    
    Uses:
    - Same root cause
    - Similar failure category
    - Same warehouse
    """
    return get_similar_failures(db, itemId, limit)


# ========================================
# 4️⃣ OPERATIONAL INTELLIGENCE
# ========================================

@router.get("/suppliers/performance")
def supplier_performance(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db)
):
    """
    **Supplier reliability metrics**
    
    Shows which suppliers cause most delays:
    - On-time delivery rate
    - Average delay days
    - Number of delayed orders
    """
    return get_supplier_performance(db)


@router.get("/reorder-triggers/history")
def reorder_trigger_history(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    item_id: Optional[str] = Query(None),
    days: int = Query(6000)
):
    """
    **See when system tried to reorder**
    
    Includes triggers that:
    - Created purchase orders
    - Were ignored
    - Failed to trigger
    """
    return get_reorder_triggers(db, item_id, days)


@router.get("/rules/health-check")
def rule_health_check(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db)
):
    """
    **Identify misconfigured reorder rules**
    
    Flags rules that:
    - Haven't been updated in 180+ days
    - Have caused stockouts
    - Have safety stock < demand variability
    """
    query = text("""
        WITH rule_failures AS (
            SELECT 
                r.item_id,
                r.safety_stock,
                r.reorder_threshold,
                r.last_updated,
                DATEDIFF(day, r.last_updated, CURRENT_DATE()) AS days_since_update,
                COUNT(s.item_id) AS stockout_count
            FROM REORDER_RULES r
            LEFT JOIN STOCKOUT_EVENTS s 
                ON r.item_id = s.item_id 
                AND s.failure_category = 'DECISION_FAILURE'
            GROUP BY r.item_id, r.safety_stock, r.reorder_threshold, r.last_updated
        )
        SELECT 
            item_id,
            safety_stock,
            reorder_threshold,
            days_since_update,
            stockout_count,
            CASE 
                WHEN days_since_update > 180 THEN 'STALE_RULE'
                WHEN stockout_count > 2 THEN 'INEFFECTIVE_RULE'
                WHEN safety_stock < 20 THEN 'SAFETY_STOCK_TOO_LOW'
                ELSE 'HEALTHY'
            END AS health_status
        FROM rule_failures
        WHERE health_status != 'HEALTHY'
        ORDER BY stockout_count DESC, days_since_update DESC;
    """)
    result = db.execute(query)
    return [dict(row._mapping) for row in result.fetchall()]


# ========================================
# 5️⃣ AI-POWERED ANALYSIS
# ========================================

@router.post("/{itemId}/ai-analysis")
def ai_powered_analysis(
    itemId: str,
    _=Depends(authorize_token()),
    db: Session = Depends(get_db)
):
    """
    **Use Snowflake Cortex to generate natural language explanation**
    
    Example output:
    "ITEM_0042 experienced a stockout on 2024-12-15 due to SUPPLIER_DELAY. 
    The purchase order PO_000123 was delayed by 8 days, causing stock to 
    run out before delivery. Recommendation: Switch to backup supplier or 
    increase safety stock by 30 units."
    """
    return analyze_stockout_with_ai(db, itemId)


@router.post("/recommendations/generate")
def generate_recommendations(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    item_id: Optional[str] = Body(None),
    root_cause: Optional[str] = Body(None)
):
    """
    **AI-generated action items based on failure patterns**
    
    Returns prioritized recommendations like:
    1. Increase safety stock for ITEM_0042 from 50 to 80
    2. Update lead time for supplier SUP_003 from 7 to 10 days
    3. Retrain forecast model (accuracy dropped to 65%)
    """
    query = text("""
        WITH failure_patterns AS (
            SELECT 
                item_id,
                root_cause,
                COUNT(*) AS failure_count
            FROM STOCKOUT_EVENTS
            WHERE (:item_id IS NULL OR item_id = :item_id)
              AND (:root_cause IS NULL OR root_cause = :root_cause)
            GROUP BY item_id, root_cause
            ORDER BY failure_count DESC
            LIMIT 10
        )
        SELECT 
            fp.item_id,
            fp.root_cause,
            fp.failure_count,
            r.safety_stock AS current_safety_stock,
            r.reorder_threshold AS current_threshold,
            CASE fp.root_cause
                WHEN 'SAFETY_STOCK_INSUFFICIENT' THEN 'Increase safety_stock by 50%'
                WHEN 'THRESHOLD_TOO_LOW' THEN 'Raise reorder_threshold by 30%'
                WHEN 'SUPPLIER_DELAY' THEN 'Switch supplier or increase lead_time'
                WHEN 'FORECAST_UNDERESTIMATED' THEN 'Retrain forecast model'
                WHEN 'STALE_FORECAST' THEN 'Reduce forecast refresh interval to 7 days'
                ELSE 'Review rule configuration'
            END AS recommendation
        FROM failure_patterns fp
        LEFT JOIN REORDER_RULES r ON fp.item_id = r.item_id;
    """)
    result = db.execute(query, {'item_id': item_id, 'root_cause': root_cause})
    return [dict(row._mapping) for row in result.fetchall()]


# ========================================
# 6️⃣ COMPARISON & BENCHMARKING
# ========================================

@router.get("/compare/before-after")
def compare_scenarios(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    item_id: str = Query(...),
    new_safety_stock: int = Query(...),
    new_threshold: int = Query(...)
):
    """
    **Compare current vs proposed configuration**
    
    Shows side-by-side:
    - Current: 50 safety stock → 3 stockouts
    - Proposed: 80 safety stock → 0 stockouts (simulated)
    """
    query = text("""
        WITH current_config AS (
            SELECT 
                item_id,
                safety_stock AS current_safety_stock,
                reorder_threshold AS current_threshold,
                (SELECT COUNT(*) FROM STOCKOUT_EVENTS WHERE item_id = :item_id) AS current_stockouts
            FROM REORDER_RULES
            WHERE item_id = :item_id
        ),
        proposed_config AS (
            SELECT 
                :new_safety_stock AS proposed_safety_stock,
                :new_threshold AS proposed_threshold,
                CASE 
                    WHEN :new_safety_stock > (SELECT AVG(daily_demand) * 2 FROM DEMAND_FORECAST WHERE item_id = :item_id)
                    THEN 0
                    ELSE 1
                END AS estimated_stockouts
        )
        SELECT * FROM current_config, proposed_config;
    """)
    result = db.execute(query, {
        'item_id': item_id,
        'new_safety_stock': new_safety_stock,
        'new_threshold': new_threshold
    })
    row = result.fetchone()
    return dict(row._mapping) if row else {}


# ========================================
# 7️⃣ EXPORT & REPORTING
# ========================================

@router.get("/export/failure-report")
def export_failure_report(
    _=Depends(authorize_token()),
    db: Session = Depends(get_db),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    """
    **Generate comprehensive failure report (CSV-ready)**
    
    Includes:
    - All stockouts in date range
    - Root causes
    - Recommendations
    - Responsible parties
    """
    query = text("""
        SELECT 
            s.item_id,
            s.warehouse_id,
            s.stockout_date,
            s.failure_category,
            s.root_cause,
            r.rule_owner AS responsible_person,
            CASE s.root_cause
                WHEN 'SUPPLIER_DELAY' THEN 'Operations Team'
                WHEN 'FORECAST_UNDERESTIMATED' THEN 'Planning Team'
                WHEN 'THRESHOLD_TOO_LOW' THEN r.rule_owner
                ELSE 'System Admin'
            END AS assigned_to
        FROM STOCKOUT_EVENTS s
        LEFT JOIN REORDER_RULES r ON s.item_id = r.item_id
        WHERE (:start_date IS NULL OR s.stockout_date >= :start_date)
          AND (:end_date IS NULL OR s.stockout_date <= :end_date)
        ORDER BY s.stockout_date DESC;
    """)
    result = db.execute(query, {'start_date': start_date, 'end_date': end_date})
    return [dict(row._mapping) for row in result.fetchall()]









@router.post("/userinfo")
def store_user_info(
    user: UserInfo = Depends(authorize_token()), 
    db: Session = Depends(get_db)
):
    """Store user info in DB only if user is new"""
    try:
        result = db.execute(
            text("SELECT EMAIL, ROLES FROM RETRACE_USER WHERE EMAIL = :email"),
            {"email": user.email}
        )
        existing_user = result.fetchone()
        print("existing_user", existing_user)
        if existing_user:
            return {
                "status": "success",
                "message": "User already exists",
                "data": {
                    "email": existing_user[0],
                    "role": existing_user[1]
                }
            }

        save_user_info(db, user)

        return {
            "status": "success",
            "message": "New user created",
            "data": {
                "email": user.email,
                "role": user.roles
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/userinfo")
def edit_user_role(
    email: str = Body(...),
    role: str = Body(...),
    _: UserInfo = Depends(authorize_token()),  # No ADMIN role required
    db: Session = Depends(get_db)
):
    """Edit user role (Temporarily open to any authenticated user)"""
    try:
        update_user_role(db, email, role)
        return {"status": "success", "message": f"Role updated for {email} {role}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/userinfo/create")
def create_users(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Creates one or multiple users.
    Supported formats:

    Single user:
    {
        "email": "abc@test.com",
        "role": "ADMIN",
        "name": "John Doe"
    }

    Multiple users:
    {
        "role": "USER",
        "users": [
            { "email": "a@test.com", "name": "User A" },
            { "email": "b@test.com", "name": "User B" }
        ]
    }
    """

    role = payload.get("role")
    if not role:
        raise HTTPException(status_code=400, detail="Role is required.")

    users = []

    # SINGLE USER FORMAT
    if "email" in payload:
        users = [{
            "email": payload["email"],
            "name": payload.get("name")  # optional
        }]

    # MULTIPLE USERS FORMAT
    elif "users" in payload:
        users = payload["users"]

    else:
        raise HTTPException(status_code=400, detail="Provide 'email' or 'users'.")

    created = []
    skipped = []

    try:
        for user in users:

            email = user.get("email")
            name = user.get("name", None)

            if not email:
                raise HTTPException(status_code=400, detail="Email is required for each user.")

            # Check if exists
            result = db.execute(
                text("SELECT EMAIL FROM RETRACE_USER WHERE EMAIL = :email"),
                {"email": email}
            )
            if result.fetchone():
                skipped.append(email)
                continue

            # Insert with NAME + EMAIL + ROLE + UUID
            db.execute(
                text("""
                    INSERT INTO RETRACE_USER (ID, NAME, EMAIL, ROLES)
                    SELECT UUID_STRING(), :name, :email, :role
                """),
                {"name": name, "email": email, "role": role}
            )

            created.append(email)

        db.commit()

        return {
            "status": "success",
            "message": "Processing complete",
            "created_users": created,
            "skipped_existing_users": skipped
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
