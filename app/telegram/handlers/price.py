from aiogram import Router, types
from app.services.price.price_service import get_current_price
from app.services.user.user_service import UserService
from app.utils.logging import get_logger, setup_logging
from app.utils.error_handler import handle_bot_errors

logger = get_logger(__name__)

router = Router()

@router.message(lambda m: (m.text or "").strip().lower() == "live price")
@handle_bot_errors("⚠️ Unable to fetch live price at the moment. Please try again later.")
async def live_price(msg: types.Message):
    if not await UserService.ensure_user_approved(msg):
        return
    price = await get_current_price()
    if price <= 0:
        await msg.answer("⚠️ Current gold price is temporarily unavailable. Please try again shortly.")
    else:
        await msg.answer(f"📊 Current Gold Price: ${price:.2f} per gram")

