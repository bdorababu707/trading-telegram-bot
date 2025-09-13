

import time
from app.db.mongo.helper import MongoHelper
from app.models.transaction import Transaction, TxStatus
from app.utils.common import generate_uuid
from app.utils.config import settings
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

class TransactionService:

    @staticmethod
    async def create_transaction(payload: dict) -> dict:
        """
        Create a buy or sell transaction document in the database based on payload.

        Args:
            payload (dict): Contains transaction details.
                For buy transactions: must include 'buy_price' or 'grams' and optionally 'buy_price_type'.
                For sell transactions: must include 'sell_price' and 'grams', optionally 'sell_price_type'.

        Returns:
            dict: Inserted transaction document.
        
        Raises:
            ValueError: If payload lacks required fields for either buy or sell.
        """

        try:
            user_id = payload["user_uuid"]
            now_ts = int(time.time())

            # Determine transaction type: buy or sell
            is_buy = "buy_price" in payload or ("grams" in payload and "buy_price" not in payload and "sell_price" not in payload)
            is_sell = "sell_price" in payload

            if is_buy:
                logger.info("Creating buy transaction")
                grams = payload["grams"]
                price = payload.get("buy_price", payload.get("price"))  # fallback on generic "price"
                price_type = payload.get("buy_price_type", "MARKET")
                total_amount = grams * price
                status = payload.get("status")
                if not status:
                    status = TxStatus.OPEN if price_type == "MARKET" else TxStatus.PENDING

                txn = Transaction(
                    uuid=await generate_uuid(),
                    user_id=user_id,
                    buy_at=payload.get("buy_at", now_ts),
                    buy_grams=grams,
                    buy_price=price,
                    buy_price_type=price_type,
                    total_buy_amount=total_amount,
                    sell_at=0,
                    sell_grams=0,
                    sell_price=0,
                    sell_price_type="",
                    total_sell_amount=0,
                    status=status,
                    updated_at=now_ts,
                    pnl=0  # Initial PNL is zero for new transactions
                )
            elif is_sell:
                logger.info("Creating sell transaction")
                grams = payload["grams"]
                price = payload["sell_price"]
                price_type = payload.get("sell_price_type", "MARKET")
                total_amount = grams * price
                status = payload.get("status")
                if not status:
                    status = TxStatus.OPEN if price_type == "MARKET" else TxStatus.PENDING

                txn = Transaction(
                    uuid=await generate_uuid(),
                    user_id=user_id,
                    buy_at=0,
                    buy_grams=0,
                    buy_price=0,
                    buy_price_type="",
                    total_buy_amount=0,
                    sell_at=payload.get("sell_at", now_ts),
                    sell_grams=grams,
                    sell_price=price,
                    sell_price_type=price_type,
                    total_sell_amount=total_amount,
                    status=status,
                    updated_at=now_ts,
                    pnl=0  # Initial PNL is zero for new transactions
                )
            else:
                raise ValueError("Payload must contain buy_price or sell_price for a valid transaction.")

            doc = txn.model_dump()
            await MongoHelper.insert_one(collection=settings.DB_TABLE.TRANSACTIONS, document=doc)
            logger.info("Transaction created: %s", doc["uuid"])
            return doc
    
        except Exception as e:
            logger.error(f"Error while creating transaction: {str(e)}")