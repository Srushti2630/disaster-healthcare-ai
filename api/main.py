"""FastAPI application factory and entry point."""
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import settings
from api.logging_utils import setup_logging
from api.middleware import RequestIDMiddleware
from api.lifespan import lifespan
from api.routes import router
from api.routes_auth import auth_router

# Setup structured logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    settings.validate_security()

    app = FastAPI(
        title="Disaster Healthcare AI Decision-Support API",
        description=(
            "An Explainable and Uncertainty-Aware AI Framework for Disaster Healthcare Demand Prediction "
            "and Multi-Objective Resource Allocation across Maharashtra's 35 Districts."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Request ID & Process Time Middleware
    app.add_middleware(RequestIDMiddleware)

    # 3. Global Exception Handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "request_id": req_id
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", None)
        logger.warning(f"Request validation failure on {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "status_code": 422,
                "message": "Input validation error",
                "details": exc.errors(),
                "request_id": req_id
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", None)
        logger.error(f"Unhandled server error on {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": 500,
                "message": "Internal server error occurred.",
                "request_id": req_id
            }
        )

    # 4. Include Endpoints Routers
    app.include_router(router)
    app.include_router(auth_router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
