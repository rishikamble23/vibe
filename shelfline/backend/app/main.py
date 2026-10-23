from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging, get_logger
from app.db.session import init_db
from app.clock import RealClock, SimClock

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

# Global clock instance (RealClock by default, can be swapped for SimClock in tests)
clock = RealClock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SHELFLINE backend", app_name=settings.APP_NAME)
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down SHELFLINE backend")


app = FastAPI(
    title=settings.APP_NAME,
    description="Deadline-Driven Dispatch for Perishable Aid",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "description": "Deadline-Driven Dispatch for Perishable Aid",
        "version": "0.1.0",
        "docs": "/docs",
    }


# Import routers here to avoid circular imports
# from app.api import batches, leases, riders, shelters, admin, ws

# app.include_router(batches.router, prefix="/batches", tags=["batches"])
# app.include_router(leases.router, prefix="/leases", tags=["leases"])
# app.include_router(riders.router, prefix="/riders", tags=["riders"])
# app.include_router(shelters.router, prefix="/shelters", tags=["shelters"])
# app.include_router(admin.router, prefix="/admin", tags=["admin"])
# app.include_router(ws.router, prefix="/ws", tags=["websocket"])