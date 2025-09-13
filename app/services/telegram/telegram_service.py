
from time import time
from typing import Any, Dict, Optional
from app.db.mongo.helper import MongoHelper
from app.utils.config import settings
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

class TelegramService:

    @staticmethod
    async def get_link_for_telegram(telegram_id: int) -> Optional[Dict[str, Any]]:
        return await MongoHelper.find_one(collection=settings.DB_TABLE.USERS, query={"telegram_id": telegram_id})

    @staticmethod
    async def get_user_by_link_code(code: str) -> Optional[Dict[str, Any]]:
        return await MongoHelper.find_one(collection=settings.DB_TABLE.USERS, query={"link_code": code})

    @staticmethod
    async def link_telegram_user(user_id: str, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Link a Telegram user to an internal user by updating the telegram_id field.

        Args:
            user_id (str): The internal user UUID.
            telegram_id (int): The Telegram ID to link.

        Returns:
            dict or None: The updated user document if successful, otherwise None.
        """
        query = {"uuid": user_id}
        update = {
            "$set": {
                "telegram_id": telegram_id,
                "updated_at": int(time.time())
            }
        }

        modified_count = await MongoHelper.update_one(
            collection=settings.DB_TABLE.USERS,
            query=query,
            update=update
        )

        if modified_count > 0:
            return await MongoHelper.find_one(
                collection=settings.DB_TABLE.USERS,
                query={"uuid": user_id}
            )

        return None
