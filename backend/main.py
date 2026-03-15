"""
SAP CAPM + Fiori Multi-Agent App Builder
FastAPI Main Application

This is the main entry point for the builder platform.
It serves both the API and the embedded Next.js frontend.

Production features:
- Rate limiting middleware
- API key authentication (optional)
- Request timing middleware
- Structured JSON logging
"""

import logging
import time
import json as json_module
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings
from backend.database import init_db, close_db

from dotenv import load_dotenv
load_dotenv()  # ← this is what's missing
# Configure logging
settings_early = get_settings()
if settings_early.log_format == "json":
    logging.basicConfig(
        level=getattr(logging, settings_early.log_level, logging.INFO),
        format='%(message)s',
    )
else:
    logging.basicConfig(
        level=getattr(logging, settings_early.log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()
    
    # Startup
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize LLM providers
    from backend.agents.llm_providers import get_llm_manager
    llm_manager = get_llm_manager()
    logger.info(f"Available LLM providers: {llm_manager.available_providers}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await close_db()


# =============================================================================
# Middleware
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP address."""

    def __init__(self, app, rpm: int = 60, burst: int = 10):
        super().__init__(app)
        self.rpm = rpm
        self.burst = burst
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if now - t < window
        ]

        if len(self._requests[client_ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limit_exceeded", "message": f"Max {self.rpm} requests/min"},
                headers={"Retry-After": "60"},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Add X-Process-Time header to every response."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)
        response.headers["X-Process-Time"] = f"{duration_ms}ms"
        return response


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="AI-powered platform for generating SAP CAPM + Fiori applications",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# Add middleware (order matters — last added = first executed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTimingMiddleware)
if settings.is_production:
    app.add_middleware(RateLimitMiddleware, rpm=settings.rate_limit_rpm, burst=settings.rate_limit_burst)


# =============================================================================
# API Routes
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from backend.agents.llm_providers import get_llm_manager
    
    llm_manager = get_llm_manager()
    
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "llm_providers": llm_manager.available_providers,
    }


@app.get("/api/config")
async def get_config():
    """Get public configuration."""
    from backend.model_catalog import get_supported_providers

    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "available_providers": settings.available_providers,
        "supported_providers": get_supported_providers(settings),
        "default_provider": settings.default_llm_provider,
        "default_model": settings.default_llm_model,
    }


@app.get("/api/config/models")
async def get_config_models(
    provider: str = Query(..., description="LLM provider identifier"),
):
    """Get model options for a specific provider."""
    from backend.model_catalog import get_provider_models

    try:
        source, models = await get_provider_models(provider, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch the live model catalog for provider '{provider}'",
        ) from exc

    return {
        "provider": provider,
        "configured": provider in settings.available_providers,
        "source": source,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models": models,
    }


# =============================================================================
# Import and include API routers
# =============================================================================

from backend.api import sessions, builder, plan, chat, copilot
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(builder.router, prefix="/api/builder", tags=["builder"])
app.include_router(plan.router, prefix="/api/builder", tags=["plan"])
app.include_router(chat.router, prefix="/api/builder", tags=["chat"])
app.include_router(copilot.router, prefix="/api/builder", tags=["copilot"])


# =============================================================================
# Next.js Static Files (for embedded frontend)
# =============================================================================

# Static files path for Next.js build output
FRONTEND_BUILD_PATH = Path(__file__).parent.parent / "frontend" / "out"

if FRONTEND_BUILD_PATH.exists():
    # Serve Next.js static files
    app.mount(
        "/_next",
        StaticFiles(directory=FRONTEND_BUILD_PATH / "_next"),
        name="nextjs_static",
    )
    
    # Serve other static assets
    if (FRONTEND_BUILD_PATH / "static").exists():
        app.mount(
            "/static",
            StaticFiles(directory=FRONTEND_BUILD_PATH / "static"),
            name="static",
        )


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# =============================================================================
# Catch-all for Next.js pages (must be last)
# =============================================================================

@app.get("/{path:path}")
async def serve_frontend(path: str):
    """
    Catch-all route to serve Next.js pages.
    In development, this redirects to the Next.js dev server.
    In production, this serves the built static files.
    """
    if not FRONTEND_BUILD_PATH.exists():
        return JSONResponse(
            status_code=200,
            content={
                "message": "Frontend not built yet",
                "api_docs": "/api/docs" if settings.debug else None,
                "health": "/api/health",
            },
        )
    
    # Try to serve the page
    page_path = FRONTEND_BUILD_PATH / path
    index_path = FRONTEND_BUILD_PATH / path / "index.html"
    
    if page_path.with_suffix(".html").exists():
        from fastapi.responses import FileResponse
        return FileResponse(page_path.with_suffix(".html"))
    elif index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    elif (FRONTEND_BUILD_PATH / "index.html").exists():
        from fastapi.responses import FileResponse
        return FileResponse(FRONTEND_BUILD_PATH / "index.html")
    
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "path": path},
    )


# =============================================================================
# Development server entry point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
