# --- app/main.py ---

import asyncio
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from app.utils.logging import get_logger, setup_logging
from app.utils.config import settings
from app.telegram.bot import start_bot_polling
from app.services.price.price_service import _websocket_price_updater
from app.db.mongo.mongodb import (
    connect_to_mongodb,
    close_mongodb_connection,
    initialize_collections,
    get_database,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global state for health endpoint
app_state = {
    "mongo_connected": False,
    "price_updater_running": False,
    "bot_running": False,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FastAPI bot app...")

    # Connect to MongoDB
    try:
        await connect_to_mongodb()
        await initialize_collections()
        app_state["mongo_connected"] = True
        logger.info("MongoDB connected")
    except Exception as e:
        app_state["mongo_connected"] = False
        logger.critical(f"MongoDB connection failed: {str(e)}")
        raise

    # Start price updater background task
    price_updater = asyncio.create_task(_websocket_price_updater())
    app_state["price_updater_running"] = True
    logger.info("WebSocket price updater started")

    # Start telegram bot polling if enabled
    telegram_bot = None
    if settings.TELEGRAM.BOT_MODE == "polling":
        telegram_bot = asyncio.create_task(start_bot_polling())
        app_state["bot_running"] = True
        logger.info("Telegram bot polling started")

    # Yield control to run the application
    yield

    # Shutdown: Cancel background tasks and close DB
    logger.info("Shutting down app...")
    if telegram_bot:
        telegram_bot.cancel()
        app_state["bot_running"] = False
    price_updater.cancel()
    app_state["price_updater_running"] = False
    await close_mongodb_connection()
    app_state["mongo_connected"] = False
    logger.info("Shutdown completed")

# FastAPI app setup
app = FastAPI(
    title=settings.APP.TITLE,
    description=settings.APP.DESCRIPTION,
    version=settings.APP.VERSION,
    docs_url=settings.APP.DOCS_URL,
    redoc_url=settings.APP.REDOC_URL,
    openapi_url=settings.APP.OPENAPI_URL,
    lifespan=lifespan
)

# Health check endpoint
@app.get("/health")
async def health_check():

    logger.info("Telegram bot health checkup")
    """Health check endpoint with service diagnostics."""
    report = {
        "status": "healthy" if all(app_state.values()) else "unhealthy",
        "database": "connected" if app_state["mongo_connected"] else "disconnected",
        "price_updater": "running" if app_state["price_updater_running"] else "stopped",
        "telegram_bot": "running" if app_state["bot_running"] else "stopped",
        "mode": "development" if settings.is_development() else "production",
        "version": settings.APP.VERSION,
    }
    # Attempt a real Mongo ping
    if app_state["mongo_connected"]:
        try:
            db = get_database()
            ping_result = await db.command("ping")
            if not ping_result:
                report["database"] = "disconnected"
        except Exception as e:
            logger.error(f"Health check: Mongo ping failed: {str(e)}")
            report["database"] = "error"
            raise HTTPException(status_code=503, detail=f"MongoDB ping failed: {str(e)}")

    logger.info(f'Telegram bot checkup report : {report}')
    return report

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting application in {'development' if settings.is_development() else 'production'} mode")
    uvicorn.run(
        "main:app",
        host=settings.SERVER.HOST,
        port=settings.SERVER.PORT,
        reload=settings.SERVER.RELOAD
    )
