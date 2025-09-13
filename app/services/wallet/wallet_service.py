from datetime import datetime
from app.models.wallet import Wallet
from app.db.mongo.helper import MongoHelper
from app.utils.common import generate_uuid
from app.utils.config import settings
from app.utils.logging import get_logger, setup_logging
import time

logger = get_logger(__name__)

class WalletService:

    @staticmethod
    async def create_wallet_for_user(user_id: str, currency: str = "AED") -> dict:

        try:
            logger.info(f"Creating wallet for user with id : {str(user_id)}")
            existing_wallet = await MongoHelper.find_one(collection=settings.DB_TABLE.WALLETS,query={"user_id": user_id, "status": "ACTIVE"})
            if existing_wallet:
                logger.info(f"Wallet exists for user : {user_id}")
                # Wallet already exists; return it instead of creating a new one
                return existing_wallet
            
            now = int(time.time())
            wallet = Wallet(
                uuid=await generate_uuid(),
                user_id=user_id,
                currency=currency,
                created_at=now,
                updated_at=now,
            )

            await MongoHelper.insert_one(collection=settings.DB_TABLE.WALLETS, document=wallet.model_dump())
            logger.info(f"Wallet created for user : {user_id}")
            return wallet.model_dump()
        
        except Exception as e:
            logger.error(f"Error creating wallet: str(e)")
    @staticmethod
    async def get_wallet_for_user(telegram_id: int) -> dict:

        try:
            logger.info(f"Fetching wallet details of user with telegram-id : {telegram_id}")
            # Translate telegram_id to user UUID if needed, or directly query by user_id field
            user = await MongoHelper.find_one(collection=settings.DB_TABLE.USERS,query={"telegram_id": telegram_id})
            if not user:
                logger.info(f"User not found with telegram-id : {telegram_id}")
                return None
            user_id = user.get("uuid")
            if not user_id:
                logger.info(f"User UUID not found for telegram-id : {telegram_id}")
                return None

            # Find wallet using user UUID
            wallet = await MongoHelper.find_one(collection=settings.DB_TABLE.WALLETS, query={"user_id": user_id, "status": "ACTIVE"})
            if not wallet:
                logger.info(f"Wallet not found for user-id : {user_id}")
                return None
            logger.info(f"Wallet found for user-id : {user_id}")
            return wallet
        except Exception as e:
            logger.error(f"Error while fetching wallet for user-id : {str(user_id)}")
    
    @staticmethod
    async def deduct_wallet_balance(user_id: str, amount: float) -> bool:
        """
        Deduct a specified amount from the active wallet balance of a user.

        Args:
            user_id (str): The unique identifier of the user.
            amount (float): The amount to deduct from the wallet.

        Returns:
            bool: True if deduction was successful (enough balance), False otherwise.
        """
        filter_criteria = {
            "user_id": user_id,
            "status": "ACTIVE",
            "balance": {"$gte": amount},  # Only proceed if balance is sufficient
        }

        update_operation = {
            "$inc": {"balance": -amount},
            "$set": {"updated_at": int(time.time())},
        }

        try:
            logger.info(f"Attempting to deduct ${amount} from user {user_id}'s wallet.")
            modified_count = await MongoHelper.update_one(
                collection=settings.DB_TABLE.WALLETS,
                query=filter_criteria,
                update=update_operation
            )

            if modified_count > 0:
                logger.info(f"Successfully deducted ${amount} from user {user_id}'s wallet.")
                return True
            else:
                logger.warning(f"Failed to deduct ${amount} from user {user_id}'s wallet. Insufficient balance or wallet not found.")
                return False

        except Exception as e:
            logger.error(f"Error during wallet deduction for user {user_id}: {e}")
            return False
