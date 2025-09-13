from aiogram import Router, types
from app.services.telegram.telegram_service import TelegramService
from app.services.positions.position_service import PositionService
from app.db.mongo.helper import MongoHelper
from app.services.user.user_service import UserService
from app.utils.config import settings
from app.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)


@router.message(lambda m: m.text and m.text.lower() == "closed positions")
async def closed_positions_handler(message: types.Message):
    if not await UserService.ensure_user_approved(message):
        return
    user = await TelegramService.get_link_for_telegram(message.from_user.id)
    if not user:
        await message.answer("⚠️ User not found. Please contact support.")
        logger.warning(f"User not found for Telegram ID {message.from_user.id}")
        return

    user_uuid = user.get("uuid")
    positions = await PositionService.get_closed_positions_with_pnl(user_uuid)
    if not positions:
        await message.answer("You have no closed positions yet.")
        return

    response_lines = ["📋 Your Closed Positions with PnL:\n"]
    for pos in positions:
        # Format buy and sell timestamps as readable dates optionally
        response_lines.append(
            f"Order ID: {pos['order_id'][:5]}\n"
            f"Bought: {pos['buy_grams']}g @ ${pos['buy_price']:.2f}\n"
            f"Sold: {pos['sell_grams']}g @ ${pos['sell_price']:.2f}\n"
            f"PnL: ${pos['pnl']:.2f}\n"
            "------------------------"
        )

    await message.answer("\n".join(response_lines))
