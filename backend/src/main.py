from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from src.core.database import init_db
from src.core.cache import cache_service
from src.core.websocket_manager import keep_connections_alive
from src.core.security_tasks import start_security_tasks, stop_security_tasks, get_security_status
from src.core.quota_scheduler import start_quota_scheduler, stop_quota_scheduler
from src.core.settings import settings
from src.routes import (
    auth, users, quotes, ai, payments, chat, documents, quota, materials, agent, onboarding,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

def _validate_production_config(cfg=settings) -> None:
    """Fail fast on misconfiguration that would silently break paid flows.

    In production mode, if Stripe is configured (secret key set) the webhook
    secret and price id must also be present — otherwise webhooks return 500
    and premium upgrade checkouts cannot be created, both of which would only
    be discovered after a paying customer hits the failure in the wild.
    Skipped in debug so local development without Stripe still boots.
    """
    if cfg.debug:
        return
    if cfg.stripe_secret_key:
        missing = []
        if not cfg.stripe_webhook_secret:
            missing.append("STRIPE_WEBHOOK_SECRET")
        if not cfg.stripe_price_id:
            missing.append("STRIPE_PRICE_ID")
        if missing:
            raise RuntimeError(
                "Stripe is configured (STRIPE_SECRET_KEY set) but the following "
                "required settings are missing: " + ", ".join(missing) +
                ". Set them in the environment or set DEBUG=true for local use."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Maler Kostenvoranschlag API...")

    _validate_production_config()

    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis cache
    await cache_service.connect()
    logger.info("Cache service initialized")

    # Warm the pytaskforce AgentFactory once — instantiating LiteLLM,
    # tool registry, etc. on the first request would otherwise add ~5s
    # latency to whatever user gets unlucky.
    try:
        from src.services.agent_service import agent_service
        await agent_service.start()
        logger.info("Agent service warmed")
    except Exception as exc:
        # If Azure creds aren't configured the factory raises on warm; we
        # log and continue so the rest of the API stays available.
        logger.warning("Agent service warm failed: %s", exc)

    # Start background tasks
    asyncio.create_task(keep_connections_alive())
    await start_security_tasks()
    await start_quota_scheduler()
    logger.info("Background tasks started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await stop_quota_scheduler()
    await stop_security_tasks()
    await cache_service.disconnect()
    logger.info("Services disconnected")

# Create FastAPI app
app = FastAPI(
    title="Maler Kostenvoranschlag API",
    description="KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe",
    version="2.1.0",
    lifespan=lifespan
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "Ein interner Serverfehler ist aufgetreten."},
    )


# Include routers
app.include_router(auth.router, tags=["authentication"])
app.include_router(users.router, tags=["users"])
app.include_router(quotes.router)
app.include_router(ai.router, tags=["ai"])
app.include_router(payments.router, tags=["payments"])
app.include_router(chat.router, tags=["chat"])
app.include_router(documents.router, tags=["documents"])
app.include_router(quota.router, tags=["quota"])
app.include_router(materials.router, tags=["materials"])
app.include_router(agent.router)
app.include_router(onboarding.router)

# Mount selected pytaskforce routers via the public host API so future
# channel adapters (Teams, Slack, additional Telegram bots) can reach the
# agent over the standard /api/v1/gateway/{channel}/* surface without us
# rebuilding ChannelLink + AgentExecutor wiring per channel.
#
# Currently exposed:
#   /api/v1/gateway/{channel}/messages  — normalized inbound payload
#   /api/v1/gateway/{channel}/webhook   — raw provider webhook (Telegram, Teams)
#   /api/v1/gateway/notify              — proactive push
#   /api/v1/gateway/channels            — list configured channels
#   /api/v1/skills, /api/v1/profiles, /api/v1/tools — discovery endpoints
#
# Telegram-Bot-Adapter (backend/src/telegram/runner.py) bleibt vorerst auf
# /api/v1/agent/bot/* weil es Pinta-User-Mapping (ChannelLink, shadow-user)
# vor jeder Mission setzt — pytaskforce' Gateway kennt die Pinta-User-Tabelle
# nicht. Wenn wir das migrieren wollen: set_gateway_components_override mit
# einem Pinta-eigenen ConversationStore + Recipient-Registry.
try:
    from taskforce.host import mount_routes
    mount_routes(
        app,
        prefix="/api/v1",
        include=["gateway", "skills", "profiles", "tools"],
    )
    logger.info("pytaskforce gateway routes mounted under /api/v1")
except Exception as exc:
    logger.warning("Could not mount pytaskforce routers: %s", exc)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Maler Kostenvoranschlag FastAPI is running"}

# WebSocket health check
@app.get("/ws-health")
async def websocket_health():
    from src.core.websocket_manager import websocket_manager
    return {
        "status": "healthy",
        "total_connections": websocket_manager.get_total_connections(),
        "connected_users": len(websocket_manager.get_connected_users())
    }

# Background task status
@app.get("/tasks-health")
async def tasks_health():
    from src.core.background_tasks import background_task_manager
    return {
        "status": "healthy",
        "running_tasks": await background_task_manager.get_running_tasks_count()
    }

# Security status
@app.get("/security-health")
async def security_health():
    security_status = await get_security_status()
    return {
        "status": "healthy" if security_status.get("running") else "stopped",
        "details": security_status
    }

# Serve static files (for production)
import os
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

