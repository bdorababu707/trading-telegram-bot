import time
from typing import Optional
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.services.transaction.transaction_service import TransactionService
from app.services.user.user_service import UserService
from app.telegram.keyboards import confirm_inline
from app.utils.common import check_retry_limit
from app.utils.logging import get_logger, setup_logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.wallet.wallet_service import WalletService
from app.services.price.price_service import get_current_price
from app.services.telegram.telegram_service import TelegramService

router = Router()

logger = get_logger(__name__)

class SellFlow(StatesGroup):
    waiting_grams = State()
    waiting_confirmation = State()

def price_selection_keyboard(current_price: float):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"Sell at current price: ${current_price:.2f}",
                callback_data="sell:current_price"
            )
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
        ]
    ])
    return kb

@router.message(lambda m: (m.text or "").strip().lower() == "sell gold")
async def sell_start(msg: types.Message, state: FSMContext):
    await state.clear()
    if not await UserService.ensure_user_approved(msg):
        return
    await msg.answer("Enter grams to sell (e.g., 1.5):")
    await state.set_state(SellFlow.waiting_grams)

# @router.message(SellFlow.waiting_grams)
# async def process_grams(msg: types.Message, state: FSMContext):
#     try:
#         grams = float(msg.text.strip())
#         if grams <= 0:
#             raise ValueError()
#     except Exception:
#         await msg.answer("❌ Invalid amount. Please enter a positive number.")
#         return

#     current_price = await get_current_price()
#     await state.update_data(grams=grams, current_price=current_price)
#     await msg.answer(
#         f"Current price per gram: ${current_price:.2f}",
#         reply_markup=price_selection_keyboard(current_price)
#     )

@router.message(SellFlow.waiting_grams)
async def process_grams(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    wrong_attempts = data.get("wrong_sell_grams", 0)  # Use same attempt key

    try:
        grams = float(msg.text.strip())
        if grams <= 0:
            raise ValueError()
    except Exception:
        can_continue = await check_retry_limit(
            msg,
            state,
            attempt_key="wrong_sell_grams",
            error_text="❌ Invalid amount. Please enter a positive number.",
            expired_text="❌ Too many invalid attempts. Selling process cancelled."
        )
        if not can_continue:
            return
        return

    # Valid input; reset counter
    await state.update_data(wrong_sell_grams=0)

    current_price = await get_current_price()
    await state.update_data(grams=grams, current_price=current_price)
    await msg.answer(
        f"Current price per gram: ${current_price:.2f}",
        reply_markup=price_selection_keyboard(current_price)
    )


@router.callback_query(F.data == "sell:current_price")
async def sell_current_price(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    grams = data.get("grams")
    current_price = data.get("current_price")
    total_price = grams * current_price

    await state.update_data(price=current_price, total_price=total_price, target_price=None)

    await call.message.edit_text(
        f"Confirm sell order:\n"
        f"Quantity: {grams}g\n"
        f"Price per gram: ${current_price:.2f}\n"
        f"Total price: ${total_price:.2f}",
        reply_markup=confirm_inline("SELL_EXECUTE")
    )
    await state.set_state(SellFlow.waiting_confirmation)
    await call.answer()

@router.callback_query(F.data == "confirm:SELL_EXECUTE")
async def confirm_sell(call: types.CallbackQuery, state: FSMContext):
    telegram_id = call.from_user.id
    try:
        data = await state.get_data()
        grams = data.get("grams")
        price_per_gram = data.get("price")  # From state set earlier
        target_price = data.get("target_price")  # For future extension; currently None or sell price

        # Step 1: User lookup
        try:
            user = await TelegramService.get_link_for_telegram(telegram_id)
            if not user:
                await call.message.edit_text("🚫 Your Telegram account isn’t linked. Please link your account or contact support.")
                await state.clear()
                return
            user_uuid = user.get("uuid")
        except Exception as ex:
            logger.error(f"User lookup failed for telegram ID {telegram_id}: {ex}")
            await call.message.edit_text("⚠️ Unable to verify your account. Please try again later.")
            await state.clear()
            return

        # Step 2: Wallet lookup
        try:
            wallet = await WalletService.get_wallet_for_user(telegram_id)
            if not wallet:
                await call.message.edit_text("🚫 No wallet found. Please contact support to set up your wallet.")
                await state.clear()
                return
        except Exception as ex:
            logger.error(f"Wallet lookup failed for user {user_uuid}: {ex}")
            await call.message.edit_text("⚠️ Unable to access your wallet. Please try again later.")
            await state.clear()
            return

        # Step 3: Verify sufficient wallet balance for sell
        total_price = grams * price_per_gram
        if wallet.get("balance", 0) < total_price:
            await call.message.edit_text("❌ Insufficient wallet balance. Please top up and try again.")
            await state.clear()
            return

        # Step 4: Create sell transaction
        try:
            txn_payload = {
                "user_uuid": user_uuid,
                "grams": grams,
                "status": None,  # Let service set default status
                "sell_price": price_per_gram,
                "sell_price_type": "MARKET" if target_price is None else "USER_DEFINED",
                "sell_at": int(time.time()),
            }
            txn = await TransactionService.create_transaction(txn_payload)
            if not txn:
                raise RuntimeError("Transaction service did not create sell order")
        except RuntimeError as ex:
            logger.error(f"Transaction creation failed for user {user_uuid}: {ex}")
            await call.message.edit_text("⚠️ Failed to place your sell order. Please try again.")
            await state.clear()
            return
        except Exception as ex:
            logger.error(f"Unexpected error on transaction creation for user {user_uuid}: {ex}")
            await call.message.edit_text("⚠️ An unexpected error occurred while placing your order. Please try later.")
            await state.clear()
            return

        # Step 5: Deduct wallet balance
        try:
            wallet_deducted = await WalletService.deduct_wallet_balance(user_uuid, total_price)
            if not wallet_deducted:
                logger.warning(f"Wallet deduction failed: insufficient funds or update error for user {user_uuid}")
                await call.message.edit_text("❌ Failed to deduct funds from wallet. Please try again or contact support.")
                await state.clear()
                return
        except Exception as ex:
            logger.error(f"Wallet deduction exception for user {user_uuid}: {ex}")
            await call.message.edit_text("⚠️ Wallet deduction failed due to system error. Please try again.")
            await state.clear()
            return

        # Success: confirm sell order to user
        msg = (
            f"✅ Sell order executed successfully!\n"
            f"Quantity: {grams}g\n"
            f"Price per gram: ${price_per_gram:.2f}\n"
            f"Total price: ${total_price:.2f}\n"
            f"Order ID: {txn['uuid']}"
        )
        await call.message.edit_text(msg)

    except Exception as ex:
        logger.error(f"Critical sell order failure for telegram ID {telegram_id}: {ex}")
        await call.message.edit_text("⚠️ An unexpected error occurred. Please try again later.")

    await state.clear()
    await call.answer()

@router.callback_query(F.data == "cancel")
async def cancel_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ Operation cancelled.")
    await state.clear()
    await call.answer()  # This is important to stop the loading spinner
    logger.info(f"User {call.from_user.id} cancelled the operation.")