from aiogram import Router
from aiogram.types import Message
from app.services.user.user_service import UserService
from app.services.wallet.wallet_service import WalletService
from app.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

@router.message(lambda message: (message.text or "").strip().lower() == "wallet")
async def wallet_balance_handler(message: Message):
    if not await UserService.ensure_user_approved(message):
        return
    telegram_id = message.from_user.id
    wallet = await WalletService.get_wallet_for_user(telegram_id)
    if not wallet:
        await message.answer("⚠️ Wallet not found. Please contact support.")
        logger.warning(f"Wallet not found for Telegram user {telegram_id}")
        return

    balance = wallet.get("balance", 0)
    currency = wallet.get("currency", "USD")
    await message.answer(f"💰 Your wallet balance is: {balance:.2f} {currency}")
