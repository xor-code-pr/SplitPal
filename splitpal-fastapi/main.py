"""
FastAPI Main Application for SplitPal
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from app.database import engine, Base
from app.routers import auth, groups, transactions, admin, balances, users

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI application"""
    # Startup
    logger.info("Starting SplitPal Backend API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    logger.info("Shutting down SplitPal Backend API...")
    await engine.dispose()


app = FastAPI(
    title="SplitPal API",
    description="Backend API for SplitPal - Expense Splitting Application",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
# Get allowed origins from environment variable or use default
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = (
    allowed_origins_str.split(",") if allowed_origins_str != "*" else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(groups.router, prefix="/api", tags=["Groups"])
app.include_router(transactions.router, prefix="/api", tags=["Transactions"])
app.include_router(balances.router, prefix="/api", tags=["Balances"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(admin.router, prefix="/api/management", tags=["Admin"])


@app.get("/api/ping")
async def ping():
    """Health check endpoint"""
    return {"message": "pong", "status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SplitPal API",
        "version": "2.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
