from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from src.core.database import init_db
from src.routes import auth, users, quotes, ai, payments

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass

# Create FastAPI app
app = FastAPI(
    title="Maler Kostenvoranschlag API",
    description="KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Maler Kostenvoranschlag FastAPI is running"}

# Serve static files (for production)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )

