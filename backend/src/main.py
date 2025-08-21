from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import logging

from core.database import init_db
from core.cache import cache_service
from core.websocket_manager import keep_connections_alive
from core.security_tasks import start_security_tasks, stop_security_tasks, get_security_status
from core.settings import settings
from routes import auth, users, quotes, ai, payments, chat, documents

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Maler Kostenvoranschlag API...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis cache
    await cache_service.connect()
    logger.info("Cache service initialized")
    
    # Start background tasks
    asyncio.create_task(keep_connections_alive())
    await start_security_tasks()
    logger.info("Background tasks started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, tags=["authentication"])
app.include_router(users.router, tags=["users"])
app.include_router(quotes.router, tags=["quotes"])
app.include_router(ai.router, tags=["ai"])
app.include_router(payments.router, tags=["payments"])
app.include_router(chat.router, tags=["chat"])
app.include_router(documents.router, tags=["documents"])

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Maler Kostenvoranschlag FastAPI is running"}

# WebSocket health check
@app.get("/ws-health")
async def websocket_health():
    from core.websocket_manager import websocket_manager
    return {
        "status": "healthy",
        "total_connections": websocket_manager.get_total_connections(),
        "connected_users": len(websocket_manager.get_connected_users())
    }

# Background task status
@app.get("/tasks-health")
async def tasks_health():
    from core.background_tasks import background_task_manager
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

