import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from fastapi import APIRouter, Request, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

from api.models import User, UserCustomStock, SimulationRecord, AllocationRecord
from api.database import get_db
from api.auth import require_role, rate_limit_simulate
from api.audit_ledger import compute_canonical_simulation_hash, compute_canonical_plan_hash

from api.schemas import (
    DistrictListResponse, MetricsResponse, BacktestResponse, BaselineResponse,
    ImpactPredictionRequest, ImpactPredictionResponse,
    LocalExplanationResponse, GlobalExplanationResponse,
    UpdateStockRequest, UserStockResponse,
    SimulationRequest, SimulationResponse,
    AllocationRequest, AllocationResponse, TransferRow,
    AllocationCreatorResponse, PendingAllocationSummary, AllocationDetailResponse,
    ClinicalForecastResponse
)
from api.services import (
    get_districts_service, get_metrics_service, get_backtest_service, get_baselines_service,
    predict_impact_service, get_global_explanation_service, explain_prediction_service,
    save_user_stock_service, get_user_stock_service, reset_user_stock_service,
    simulate_service, allocate_service,
    get_clinical_forecast_service
)

router = APIRouter()

# -------------------------------------------------------------
# HEALTH & READINESS PROBES
# -------------------------------------------------------------
@router.get("/health", summary="Liveness Probe", tags=["System"])
@router.get("/api/health", summary="Liveness Probe (API alias)", tags=["System"])
async def health_check() -> Dict[str, str]:
    """Basic liveness check verifying the HTTP event loop is responding."""
    return {"status": "ok"}

@router.get("/ready", summary="Readiness Probe", tags=["System"])
@router.get("/api/ready", summary="Readiness Probe (API alias)", tags=["System"])
async def readiness_check(request: Request) -> Dict[str, Any]:
    """
    Readiness check verifying all critical artifacts (data, models, distance matrix) are loaded in memory.
    Returns HTTP 503 if the backend is still initializing or missing required models.
    """
    is_ready = getattr(request.app.state, "ready", False)
    pop_loaded = hasattr(request.app.state, "pop_df") and not request.app.state.pop_df.empty
    geojson_loaded = hasattr(request.app.state, "geojson") and len(request.app.state.geojson.get("features", [])) > 0
    models_loaded = hasattr(request.app.state, "impact_bundle") and request.app.state.impact_bundle is not None
    surrogate_loaded = hasattr(request.app.state, "surrogate_bundle") and request.app.state.surrogate_bundle is not None
    shap_loaded = hasattr(request.app.state, "shap_explainer") and request.app.state.shap_explainer is not None
    dist_loaded = hasattr(request.app.state, "distances_df") and request.app.state.distances_df is not None
    clinical_loaded = hasattr(request.app.state, "clinical_model") and request.app.state.clinical_model is not None

    if not is_ready or not (pop_loaded and dist_loaded and models_loaded and clinical_loaded):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is not ready: required data or model artifacts are still loading or unavailable."
        )

    return {
        "status": "ready",
        "artifacts_loaded": {
            "districts_data": pop_loaded,
            "geojson": geojson_loaded,
            "impact_model": models_loaded,
            "surrogate_classifier": surrogate_loaded,
            "shap_explainer": shap_loaded,
            "distance_matrix": dist_loaded,
            "clinical_model": clinical_loaded
        }
    }

# -------------------------------------------------------------
# DATA & GEO ENDPOINTS
# -------------------------------------------------------------
@router.get("/api/districts", response_model=DistrictListResponse, summary="Get 35 Maharashtra Districts", tags=["Data"])
async def get_districts(request: Request):
    """Retrieve all 35 Maharashtra districts with population, bed capacities, and facilities with provenance tags."""
    return get_districts_service(request.app.state)

@router.get("/api/geo/districts", summary="Get Normalised GeoJSON Boundaries", tags=["Data"])
async def get_district_geojson(request: Request):
    """Retrieve normalized Maharashtra 35-district GeoJSON polygon boundaries (REAL data)."""
    geojson = getattr(request.app.state, "geojson", None)
    if not geojson or not geojson.get("features"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GeoJSON boundary file not available.")
    return JSONResponse(content=geojson)

@router.get("/api/metrics", response_model=MetricsResponse, summary="Get Model Benchmark Metrics & Limitations", tags=["Evaluation"])
async def get_metrics(request: Request):
    """Retrieve time-split benchmark metrics, CQR interval coverage, surrogate fidelity, and methodology limitations."""
    return get_metrics_service(request.app.state)

@router.get("/api/backtest", response_model=BacktestResponse, summary="Get Historical Disaster Backtest", tags=["Evaluation"])
async def get_backtest(request: Request):
    """Retrieve Leave-One-Event-Out historical replay on real EM-DAT India disasters."""
    return get_backtest_service(request.app.state)

@router.get("/api/baselines", response_model=BaselineResponse, summary="Get Optimizer 20-Scenario Baseline Comparison", tags=["Evaluation"])
async def get_baselines(request: Request):
    """Retrieve 20-scenario optimization comparison across SCIP MIP and 4 heuristic baselines."""
    return get_baselines_service(request.app.state)

@router.get("/api/baselines/pareto-plot", summary="Get Optimizer Pareto Sweep Plot Image", tags=["Evaluation"])
async def get_pareto_plot():
    """Return Pareto frontier trade-off image between cost index and unmet demand."""
    plot_path = Path("reports/pareto_sweep.png")
    if not plot_path.exists():
        plot_path = Path("reports/baseline_comparison_plot.png")
    if not plot_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pareto plot image not found.")
    return FileResponse(plot_path, media_type="image/png")

# -------------------------------------------------------------
# DECISION SUPPORT & SIMULATION ENDPOINTS
# -------------------------------------------------------------
@router.post("/api/predict-impact", response_model=ImpactPredictionResponse, summary="Predict Casualty Impact & Interval", tags=["Impact"])
async def predict_impact(request: Request, body: ImpactPredictionRequest):
    """Predict point casualty impact and CQR 90% uncertainty prediction interval."""
    return predict_impact_service(request.app.state, body)

@router.get("/api/explain/global", response_model=GlobalExplanationResponse, summary="Get Global SHAP Feature Importances", tags=["Explainability"])
async def get_global_explanation(request: Request):
    """Retrieve global model feature importances and base64-encoded SHAP summary plot."""
    return get_global_explanation_service(request.app.state)

@router.get("/api/explain/summary-plot", summary="Get Saved SHAP Summary Plot Image", tags=["Explainability"])
async def get_shap_summary_plot():
    """Return raw saved SHAP summary plot PNG image."""
    plot_path = Path("reports/shap_summary.png")
    if not plot_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SHAP summary plot not generated.")
    return FileResponse(plot_path, media_type="image/png")

@router.post("/api/explain", response_model=LocalExplanationResponse, summary="Explain Casualty Prediction via Ridge SHAP", tags=["Explainability"])
async def explain_prediction(request: Request, body: ImpactPredictionRequest):
    """Explain Ridge model prediction via exact linear decomposition (beta * z) with optional XGBoost Tree-SHAP comparison."""
    return await run_in_threadpool(explain_prediction_service, request.app.state, body)

@router.post("/api/stock", response_model=UserStockResponse, summary="Upload or Edit Custom District Stocks", tags=["Inventory"])
async def upload_or_edit_stock(
    body: UpdateStockRequest,
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Upload or edit district-by-medicine stock stored per user with USER-PROVIDED provenance tag."""
    return save_user_stock_service(db, current_user, body)

@router.get("/api/stock", response_model=UserStockResponse, summary="Get User Custom Stocks", tags=["Inventory"])
async def get_user_stock(
    current_user: User = Depends(require_role(["officer", "coordinator", "admin", "viewer"])),
    db: Session = Depends(get_db)
):
    """Retrieve active custom stocks for current user."""
    return get_user_stock_service(db, current_user)

@router.delete("/api/stock", response_model=UserStockResponse, summary="Reset Custom District Stocks", tags=["Inventory"])
async def reset_user_stock(
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Clear custom stocks to revert to baseline estimated stock."""
    return reset_user_stock_service(db, current_user)

@router.post("/api/stock/reset", response_model=UserStockResponse, summary="Reset Custom District Stocks (POST alternative)", tags=["Inventory"])
async def reset_user_stock_post(
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Clear custom stocks to revert to baseline estimated stock."""
    return reset_user_stock_service(db, current_user)

@router.post("/api/simulate", response_model=SimulationResponse, summary="Execute Monte-Carlo Demand Simulation", tags=["Simulation"])
async def simulate_scenario(
    request: Request,
    body: SimulationRequest,
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Execute 2,000-draw Monte-Carlo demand simulation and shortage risk classification across districts."""
    rate_limit_simulate(request)

    # Task E: Extract user custom stock before threadpool offload, passing plain dict
    user_custom_map: Dict[str, Dict[str, float]] = {}
    if body.custom_stocks:
        user_custom_map = body.custom_stocks
    elif current_user is not None and db is not None:
        try:
            custom_rows = db.query(UserCustomStock).filter(UserCustomStock.user_id == current_user.id).all()
            for r in custom_rows:
                if r.district not in user_custom_map:
                    user_custom_map[r.district] = {}
                user_custom_map[r.district][r.medicine] = float(r.quantity)
        except Exception as e:
            logger.warning(f"Error querying UserCustomStock: {e}")

    # Compute simulation in threadpool
    res: SimulationResponse = await run_in_threadpool(simulate_service, request.app.state, body, custom_stocks=user_custom_map)

    # DEF-3C-01: Persist SimulationRecord in request/database thread
    try:
        inputs_dict = {
            "epicentre": body.epicentre,
            "hazard": body.hazard.value if hasattr(body.hazard, "value") else str(body.hazard),
            "severity": float(body.severity),
            "planning_level": body.planning_level.value if hasattr(body.planning_level, "value") else str(body.planning_level),
            "stock_adjustment_pct": float(body.stock_adjustment_pct),
            "affected_override": body.affected_override,
            "custom_stocks": user_custom_map if user_custom_map else None
        }
        canonical_inputs_json, results_hash = compute_canonical_simulation_hash(inputs_dict, res.results)

        sim_record = SimulationRecord(
            id=res.simulation_id,
            user_id=current_user.id if current_user else None,
            inputs_json=canonical_inputs_json,
            results_hash=results_hash,
            created_at=datetime.now(timezone.utc)
        )
        db.add(sim_record)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist SimulationRecord: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist simulation record to database."
        )

    return res

@router.post("/api/allocate", response_model=AllocationResponse, summary="Solve Resource Allocation MIP", tags=["Optimization"])
async def allocate_resources(
    request: Request,
    body: AllocationRequest,
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Solve multi-objective MIP resource allocation problem using Google OR-Tools SCIP solver."""
    # DEF-3C-02: Validate simulation_id if provided
    sim_record = None
    if body.simulation_id:
        sim_record = db.query(SimulationRecord).filter(SimulationRecord.id == body.simulation_id).first()
        if not sim_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Simulation '{body.simulation_id}' not found. Cannot link allocation to a nonexistent simulation."
            )

    # Task E: Extract user custom stock before threadpool offload, passing plain dict
    user_custom_map: Dict[str, Dict[str, float]] = {}
    if body.custom_stocks:
        user_custom_map = body.custom_stocks
    elif current_user is not None and db is not None:
        try:
            custom_rows = db.query(UserCustomStock).filter(UserCustomStock.user_id == current_user.id).all()
            for r in custom_rows:
                if r.district not in user_custom_map:
                    user_custom_map[r.district] = {}
                user_custom_map[r.district][r.medicine] = float(r.quantity)
        except Exception as e:
            logger.warning(f"Error querying UserCustomStock: {e}")

    # Run optimizer in threadpool
    res: AllocationResponse = await run_in_threadpool(allocate_service, request.app.state, body, custom_stocks=user_custom_map)

    # DEF-3C-02: Compute canonical plan hash and persist AllocationRecord
    try:
        transfers_json, plan_hash = compute_canonical_plan_hash(res.transfers)
        alloc_id = str(uuid.uuid4())
        alloc_status = "PENDING_REVIEW" if body.simulation_id else "UNLINKED_LEGACY"

        alloc_record = AllocationRecord(
            id=alloc_id,
            simulation_id=body.simulation_id if body.simulation_id else None,
            user_id=current_user.id if current_user else None,
            plan_hash=plan_hash,
            transfers_json=transfers_json,
            status=alloc_status,
            cost_index=res.cost_index,
            unmet_demand_after=res.unmet_demand_after,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(alloc_record)
        db.commit()

        # Attach identifiers and plan hash to response
        res.allocation_id = alloc_id
        res.simulation_id = body.simulation_id
        res.plan_hash = plan_hash
        res.status = alloc_status
    except Exception as e:
        logger.error(f"Failed to persist AllocationRecord: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist allocation record to database."
        )

    return res

# -------------------------------------------------------------
# ALLOCATION RETRIEVAL & GOVERNANCE QUEUE ENDPOINTS
# -------------------------------------------------------------
def _parse_transfers(transfers_json: Optional[str]) -> Tuple[List[TransferRow], int, int]:
    """
    Parse canonical transfers JSON into validated TransferRow objects and summary metrics.
    Ensures deterministic sorting by (source_region, dest_region, medicine).
    Returns (shipments, transfers_count, total_transferred_units).
    """
    if not transfers_json:
        return [], 0, 0
    try:
        raw_list = json.loads(transfers_json)
        if not isinstance(raw_list, list):
            return [], 0, 0
        shipments: List[TransferRow] = []
        total_units = 0
        for item in raw_list:
            if isinstance(item, dict):
                row = TransferRow(
                    source_region=str(item.get("source_region", "")),
                    dest_region=str(item.get("dest_region", "")),
                    medicine=str(item.get("medicine", "")),
                    quantity=int(item.get("quantity", 0)),
                    distance_km=round(float(item.get("distance_km", 0.0)), 2),
                    cost_index=round(float(item.get("cost_index", 0.0)), 2),
                    priority=str(item.get("priority", "STANDARD")),
                    confidence=round(float(item.get("confidence", 0.85)), 3)
                )
                shipments.append(row)
                total_units += row.quantity
        shipments.sort(key=lambda s: (s.source_region, s.dest_region, s.medicine))
        return shipments, len(shipments), total_units
    except Exception as e:
        logger.warning(f"Failed to parse transfers_json: {e}")
        return [], 0, 0


@router.get(
    "/api/allocations/pending",
    response_model=List[PendingAllocationSummary],
    summary="Get Pending Allocations for Governance Review",
    tags=["Allocation & Governance"]
)
async def get_pending_allocations(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of allocations to return (1-100)"),
    offset: int = Query(default=0, ge=0, description="Pagination offset (>= 0)"),
    current_user: User = Depends(require_role(["coordinator", "admin", "officer", "viewer"])),
    db: Session = Depends(get_db)
):
    """
    Retrieve persisted allocations currently in PENDING_REVIEW status for governance review.
    - Returns only actual records persisted in SQLite.
    - Excludes APPROVED, REJECTED, and UNLINKED_LEGACY allocations.
    - Stable ordering: newest first by created_at descending.
    - Avoids N+1 database queries via joinedload on creator user.
    - Handles empty queue with HTTP 200 and an empty list [].
    """
    allocations = (
        db.query(AllocationRecord)
        .options(joinedload(AllocationRecord.user))
        .filter(AllocationRecord.status == "PENDING_REVIEW")
        .order_by(desc(AllocationRecord.created_at), desc(AllocationRecord.id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    results: List[PendingAllocationSummary] = []
    for alloc in allocations:
        _, transfers_count, total_units = _parse_transfers(alloc.transfers_json)
        creator_info = None
        if alloc.user:
            creator_info = AllocationCreatorResponse(
                id=alloc.user.id,
                email=alloc.user.email,
                role=alloc.user.role
            )

        created_str = alloc.created_at.isoformat() if hasattr(alloc.created_at, "isoformat") else str(alloc.created_at)
        updated_str = alloc.updated_at.isoformat() if hasattr(alloc.updated_at, "isoformat") else str(alloc.updated_at)

        results.append(
            PendingAllocationSummary(
                allocation_id=alloc.id,
                id=alloc.id,
                simulation_id=alloc.simulation_id,
                plan_hash=alloc.plan_hash,
                status=alloc.status,
                cost_index=alloc.cost_index,
                unmet_demand_after=alloc.unmet_demand_after,
                transfers_count=transfers_count,
                total_transferred_units=total_units,
                created_at=created_str,
                updated_at=updated_str,
                creator=creator_info
            )
        )
    return results


@router.get(
    "/api/allocations/{allocation_id}",
    response_model=AllocationDetailResponse,
    summary="Get Specific Allocation Record and Shipments",
    tags=["Allocation & Governance"]
)
async def get_allocation_by_id(
    allocation_id: str,
    current_user: User = Depends(require_role(["coordinator", "admin", "officer", "viewer"])),
    db: Session = Depends(get_db)
):
    """
    Retrieve one persisted allocation and its constituent shipment rows.
    - Validates referenced simulation exists when the record claims to be linked.
    - Preserves historical UNLINKED_LEGACY status for unlinked allocations without fabricating simulation IDs.
    - Returns HTTP 404 for nonexistent allocations or nonexistent referenced simulations.
    - Deterministically sorts shipments by (source_region, dest_region, medicine).
    - Protects user privacy by never exposing sensitive authentication fields.
    """
    alloc = (
        db.query(AllocationRecord)
        .options(joinedload(AllocationRecord.user))
        .filter(AllocationRecord.id == allocation_id)
        .first()
    )
    if not alloc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation '{allocation_id}' not found."
        )

    # Validate referenced simulation if record claims to be linked
    if alloc.simulation_id:
        sim = db.query(SimulationRecord).filter(SimulationRecord.id == alloc.simulation_id).first()
        if not sim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced simulation '{alloc.simulation_id}' not found for allocation '{allocation_id}'."
            )

    shipments, transfers_count, total_units = _parse_transfers(alloc.transfers_json)
    creator_info = None
    if alloc.user:
        creator_info = AllocationCreatorResponse(
            id=alloc.user.id,
            email=alloc.user.email,
            role=alloc.user.role
        )

    created_str = alloc.created_at.isoformat() if hasattr(alloc.created_at, "isoformat") else str(alloc.created_at)
    updated_str = alloc.updated_at.isoformat() if hasattr(alloc.updated_at, "isoformat") else str(alloc.updated_at)

    return AllocationDetailResponse(
        allocation_id=alloc.id,
        id=alloc.id,
        simulation_id=alloc.simulation_id,
        plan_hash=alloc.plan_hash,
        status=alloc.status,
        cost_index=alloc.cost_index,
        unmet_demand_after=alloc.unmet_demand_after,
        transfers_count=transfers_count,
        total_transferred_units=total_units,
        created_at=created_str,
        updated_at=updated_str,
        creator=creator_info,
        shipments=shipments
    )

# -------------------------------------------------------------
# CLINICAL FORECASTING ENDPOINT
# -------------------------------------------------------------
@router.get("/api/forecast/clinical", response_model=ClinicalForecastResponse, summary="Clinical Specialty Demand Forecast", tags=["Forecasting"])
async def get_clinical_forecast(
    request: Request,
    horizon_months: int = Query(default=6, ge=1, le=12, description="Forecast horizon in months (1-12)"),
    service: Optional[str] = Query(default=None, description="Optional clinical service filter (ICU, Emergency, General Medicine, Surgery)")
):
    """
    Generate recursive multi-step clinical forecasts across healthcare specialties
    with empirical 90% prediction intervals calibrated from pre-holdout temporal residuals.
    """
    return await run_in_threadpool(get_clinical_forecast_service, request.app.state, horizon_months=horizon_months, service=service)
