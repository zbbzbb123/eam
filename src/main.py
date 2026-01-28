"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import init_db
from src.api.holdings import router as holdings_router
from src.api.quotes import router as quotes_router
from src.api.portfolio import router as portfolio_router
from src.api.signals import router as signals_router
from src.api.reports import router as reports_router
from src.api.analyzers import router as analyzers_router
from src.api.ai import router as ai_router
from src.scheduler.scheduler import router as scheduler_router, get_scheduler_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    init_db()
    scheduler = get_scheduler_service()
    scheduler.start()
    scheduler.setup_default_jobs()
    yield
    # Shutdown
    scheduler.stop()


app = FastAPI(
    title="EAM - Easy Asset Management",
    description="Personal Investment Decision System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(holdings_router, prefix="/api")
app.include_router(quotes_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(signals_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(analyzers_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
