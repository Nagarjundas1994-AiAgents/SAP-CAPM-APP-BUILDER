"""
SAP CAPM + Fiori Multi-Agent App Builder
FastAPI Main Application

This is the main entry point for the builder platform.
It serves both the API and the embedded Next.js frontend.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="AI-powered platform for generating SAP CAPM + Fiori applications",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    from backend.agents.llm_providers import get_llm_manager
    
    llm_manager = get_llm_manager()
    
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "available_providers": llm_manager.available_providers,
        "default_provider": settings.default_llm_provider,
    }


# =============================================================================
# Import and include API routers
# =============================================================================

from backend.api import sessions, builder
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(builder.router, prefix="/api/builder", tags=["builder"])


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
