import logging
from typing import Optional
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.utils.config import settings

# Get logger
logger = logging.getLogger(__name__)

# Global database client and connection
_db_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

async def connect_to_mongodb() -> None:
    """
    Connect to MongoDB using static values.
    This should be called once at application startup.
    """
    global _db_client, _db

    if _db_client is not None:
        logger.warning("MongoDB connection already established")
        return
    
    # Get MongoDB settings from config
    mongo_settings = {
        "maxPoolSize": settings.DB.MAX_POOL_SIZE,
        "minPoolSize": settings.DB.MIN_POOL_SIZE,
        "maxIdleTimeMS": settings.DB.MAX_IDLE_TIME_MS,
        "serverSelectionTimeoutMS": settings.DB.SERVER_SELECTION_TIMEOUT_MS,
        "connectTimeoutMS": settings.DB.CONNECT_TIMEOUT_MS
    }

    logger.info(f"Connecting to MongoDB at {settings.DB.URL}")
    try:
        # Connect to MongoDB
        _db_client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.DB.URL, **mongo_settings
        )

        # Verify connection is successful with a ping
        await _db_client.admin.command('ping')

        # Get database instance
        _db = _db_client[settings.DB.DB_NAME]

        logger.info(f"Connected to MongoDB. Database: {settings.DB.DB_NAME}")

        # Log available collections
        collection_names = await _db.list_collection_names()
        logger.debug(f"Available collections: {', '.join(collection_names)}")

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.critical(f"Failed to connect to MongoDB: {str(e)}")
        raise

async def close_mongodb_connection() -> None:
    """
    Close MongoDB connection.
    This should be called once at application shutdown.
    """
    global _db_client

    if _db_client is None:
        logger.warning("No MongoDB connection to close")
        return

    logger.info("Closing MongoDB connection")
    _db_client.close()
    _db_client = None
    logger.info("MongoDB connection closed")

def get_database() -> AsyncIOMotorDatabase:
    """
    Get the database instance.
    This function can be used as a dependency in FastAPI.

    Returns:
        AsyncIOMotorDatabase: MongoDB database instance

    Raises:
        RuntimeError: If database connection hasn't been established
    """
    if _db is None:
        raise RuntimeError(
            "Database connection not established. "
            "Ensure connect_to_mongodb() is called during startup."
        )
    return _db

async def initialize_collections() -> None:
    """
    Initialize collections and create indices.
    This runs once during application startup.
    """
    db = get_database()

    try:
        await db[settings.DB_TABLE.USERS].create_index("telegram_id", unique=True)
        # await db[settings.DB_TABLE.ORDER_TRANSACTIONS].create_index("phone_number", unique=True)
        logger.info("MongoDB collections and indices initialized")
    except Exception as e:
        logger.error(f"Error initializing MongoDB collections: {str(e)}")
        raise