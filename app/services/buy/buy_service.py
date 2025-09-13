
import time
from app.services.telegram.telegram_service import TelegramService
from app.services.price.price_service import get_current_price
from app.services.transaction.transaction_service import TransactionService
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

class BuyService:

    @staticmethod
    async def create_buy_order_for_linked_user(telegram_id: int, grams: float, custom_price: float = None):
        try:
            link = await TelegramService.get_link_for_telegram(telegram_id)
            if not link:
                logger.info(f"user not linked for telegram id : {telegram_id}")
                raise RuntimeError("telegram not linked")
            rate = await get_current_price()
            buy_at = int(time.time())

            if custom_price is None:
                # Immediate market order
                price_per_gram = rate
                price_type = "MARKET"
            else:
                # Limit order (pending)
                price_per_gram = custom_price
                price_type = "USER_DEFINED"

            buy_price_total = grams * price_per_gram

            buy_transaction_payload = {
                "user_uuid": link["uuid"],
                "buy_at": buy_at,
                "grams": grams,
                "buy_price": price_per_gram,
                "buy_price_type": price_type,
                "status": None,   # Let create_transaction set status
            }

            return await TransactionService.create_transaction(buy_transaction_payload)
        
        except Exception as e:
            logger.error(f"Error while creating buy order for user with telegram id : {telegram_id} = {str(e)}")