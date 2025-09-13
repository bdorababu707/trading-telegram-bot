import secrets
import time
from typing import Dict, Any
from app.models.user import UserLink
from app.db.mongo.helper import MongoHelper
from app.utils.common import generate_uuid
from app.utils.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

class UserService:
    @staticmethod
    async def create_telegram_user(
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        phone_number: str = None,
        status: str = "PENDING"
    ) -> Dict[str, Any]:
        """Ensure a user exists and update fields if changed"""

        collection = settings.DB_TABLE.USERS
        existing = await MongoHelper.find_one(collection=collection, query={"telegram_id": telegram_id})

        if existing:
            update_fields = {}

            if existing.get("username") != username:
                update_fields["username"] = username

            if existing.get("first_name") != first_name:
                update_fields["first_name"] = first_name

            if existing.get("last_name") != last_name:
                update_fields["last_name"] = last_name

            if phone_number and existing.get("phone_number") != phone_number:
                update_fields["phone_number"] = phone_number

            if update_fields:
                await MongoHelper.update_one(
                    collection=collection,
                    query={"telegram_id": telegram_id},
                    update={"$set": update_fields}
                )
                logger.info("Updated user fields for telegram_id %s: %s", telegram_id, update_fields)

            return {**existing, **update_fields}

        # Create user if not exists
        link_code = secrets.token_hex(4)
        user = UserLink(
            uuid=await generate_uuid(),
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            created_at=int(time.time()),
            link_code=link_code,
            status=status,
            phone_number=phone_number
        )

        doc = user.model_dump(exclude_none=True)

        if doc.get("email") is None:
            doc.pop("email", None)

        await MongoHelper.insert_one(collection=collection, document=doc)
        logger.info("Created telegram user %s", telegram_id)
        return doc

    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int) -> Dict[str, Any]:
        """Fetch user by telegram_id"""
        try:
            logger.debug("Fetching user by telegram_id: %s", telegram_id)
            collection = settings.DB_TABLE.USERS
            user = await MongoHelper.find_one(collection=collection, query={"telegram_id": telegram_id})
            logger.debug("Fetched user: %s", user)
            return user
        except Exception as e:
            logger.error("Error fetching user by telegram_id %s: %s", telegram_id, e)
            return None

    @staticmethod
    async def ensure_user_approved(message) -> bool:
        user = await UserService.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("Please send hi, hello before proceeding to any action")
            return False
        if user.get("status") != "APPROVED":
            await message.answer("Your account verification is in progress. Please wait for admin approval.")
            return False
        return True
