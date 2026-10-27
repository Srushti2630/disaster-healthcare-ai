from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from api.models import User
from api.database import get_db
from api.auth import require_role, rate_limit_simulate

from api.schemas import (
    DistrictListResponse, MetricsResponse, BacktestResponse, BaselineResponse,
    HistoricalAllocationScenario,
    ImpactPredictionRequest, ImpactPredictionResponse,
    LocalExplanationResponse, GlobalExplanationResponse,
    UpdateStockRequest, UserStockResponse,
    SimulationRequest, SimulationResponse,
    AllocationRequest, AllocationResponse
)
from api.services import (
    get_districts_service, get_metrics_service, get_backtest_service, get_baselines_service,
    predict_impact_service, get_global_explanation_service, explain_prediction_service,
    save_user_stock_service, get_user_stock_service, reset_user_stock_service,
    simulate_service, allocate_service, export_pdf_service, get_historical_allocation_scenarios
)

router = APIRouter()

# -------------------------------------------------------------
# HEALTH & READINESS PROBES
# -------------------------------------------------------------
@router.get("/health", summary="Liveness Probe", tags=["System"])
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}

@router.get("/ready", summary="Readiness Probe", tags=["System"])
async def readiness_check(request: Request) -> Dict[str, Any]:
    is_ready = getattr(request.app.state, "ready", False)
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is still initializing or missing required models/data."
        )
    return {
        "status": "ready",
        "artifacts_loaded": {
            "districts_data": not request.app.state.pop_df.empty,
            "geojson": len(request.app.state.geojson.get("features", [])) > 0,
            "impact_model": request.app.state.impact_bundle is not None,
            "distance_matrix": request.app.state.distances_df is not None
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

@router.get("/api/baselines", response_model=BaselineResponse, summary="Get Stratified Optimizer Baseline Comparison", tags=["Evaluation"])
async def get_baselines(request: Request):
    """Retrieve the completed stratified comparison across SCIP MIP and 4 heuristic baselines."""
    return get_baselines_service(request.app.state)

@router.get(
    "/api/allocation/scenarios",
    response_model=List[HistoricalAllocationScenario],
    summary="Get Maharashtra EM-DAT Reference Scenarios",
    tags=["Allocation"]
)
async def get_allocation_scenarios():
    """Return real EM-DAT affected totals for Maharashtra district or multi-district events."""
    return get_historical_allocation_scenarios()

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
    return explain_prediction_service(request.app.state, body)

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
    return simulate_service(request.app.state, body, user=current_user, db=db)

@router.post("/api/allocate", response_model=AllocationResponse, summary="Solve Resource Allocation MIP", tags=["Optimization"])
async def allocate_resources(
    request: Request,
    body: AllocationRequest,
    current_user: User = Depends(require_role(["officer", "coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """Solve multi-objective MIP resource allocation problem using Google OR-Tools SCIP solver."""
    return allocate_service(request.app.state, body, user=current_user, db=db)

@router.post("/api/export/pdf-sitrep", summary="Generate & Download Official NDMA Incident Report PDF", tags=["Reporting"])
async def export_pdf_sitrep(
    request: Request,
    body: AllocationRequest,
    current_user: User = Depends(require_role(["officer", "coordinator", "admin", "viewer"])),
    db: Session = Depends(get_db)
):
    """Generate official NDMA/SDMA executive situation report PDF with OR-Tools transfers and SHA-256 seal."""
    pdf_path = export_pdf_service(request.app.state, body, user=current_user, db=db)
    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Failed to generate PDF situation report.")
    hazard_name = body.hazard.value if hasattr(body.hazard, "value") else body.hazard
    filename = f"NDMA_SITREP_{body.epicentre or 'Maharashtra'}_{hazard_name}.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
