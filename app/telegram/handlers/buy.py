
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.telegram.keyboards import confirm_inline
from app.services.buy.buy_service import BuyService
from app.services.price.price_service import get_current_price
from app.services.wallet.wallet_service import WalletService
from app.services.telegram.telegram_service import TelegramService
from app.services.user.user_service import UserService
from app.utils.common import check_retry_limit, inactivity_timeout_guard
from app.utils.logging import get_logger, setup_logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

logger = get_logger(__name__)

class BuyFlow(StatesGroup):
    waiting_grams = State()
    # waiting_price_input = State()
    waiting_confirmation = State()

def price_selection_keyboard(current_price: float):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"Buy at current price: ${current_price:.2f}",
                callback_data="buy:current_price"
            )
        ],
        # [
        #     InlineKeyboardButton(
        #         text="Set custom price",
        #         callback_data="buy:custom_price"
        #     )
        # ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
        ]
    ])
    return kb

@router.message(lambda m: (m.text or "").strip().lower() == "buy gold")
async def buy_start(msg: types.Message, state: FSMContext):
    await state.clear()
    if not await UserService.ensure_user_approved(msg):
        return
    await msg.answer("Enter grams to buy (e.g., 1.5):")
    await state.set_state(BuyFlow.waiting_grams)

# @router.message(BuyFlow.waiting_grams)
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

@inactivity_timeout_guard()
@router.message(BuyFlow.waiting_grams)
async def process_grams(msg: types.Message, state: FSMContext):
    try:
        logger.info(f"Taking input grams: {msg.text} from user {msg.from_user.id} for BUY")
        grams = float(msg.text.strip())
        if grams <= 0:
            raise ValueError()
    except Exception:
        can_continue = await check_retry_limit(
            message=msg,
            state=state,
            attempt_key="wrong_grams_attempts",
            error_text="❌ Invalid amount. Please enter a positive number.",
            expired_text="❌ Too many invalid attempts! Session expired. Please start again."
        )
        if not can_continue:
            return
        return

    # Valid input; reset retry count for grams
    await state.update_data(wrong_grams_attempts=0)

    current_price = await get_current_price()
    await state.update_data(grams=grams, current_price=current_price)
    await msg.answer(
        f"Current price per gram: ${current_price:.2f}",
        reply_markup=price_selection_keyboard(current_price)
    )

@inactivity_timeout_guard()
@router.callback_query(F.data == "buy:current_price")
async def buy_current_price(call: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {call.from_user.id} selected BUY at current price")
    data = await state.get_data()
    grams = data.get("grams")
    current_price = data.get("current_price")
    total_price = grams * current_price

    await state.update_data(price=current_price, total_price=total_price, target_price=None)

    await call.message.edit_text(
        f"Confirm buy order:\n"
        f"Quantity: {grams}g\n"
        f"Price per gram: ${current_price:.2f}\n"
        f"Total price: ${total_price:.2f}",
        reply_markup=confirm_inline("BUY_EXECUTE")
    )
    await state.set_state(BuyFlow.waiting_confirmation)
    await call.answer()

@inactivity_timeout_guard()
@router.callback_query(F.data.in_(["confirm:BUY_EXECUTE", "confirm:BUY_PENDING"]))
async def confirm_buy(call: types.CallbackQuery, state: FSMContext):
    telegram_id = call.from_user.id
    logger.info(f"User {telegram_id} confirmed BUY order with action {call.data}")
    try:
        data = await state.get_data()
        grams = data.get("grams")
        target_price = data.get("target_price")
        current_price = data.get("current_price")

        # Step 1: Check user-link
        try:
            user = await TelegramService.get_link_for_telegram(telegram_id)
            if not user:
                await call.message.edit_text("🚫 Your Telegram account isn’t linked. Please link your account or contact support.")
                await state.clear()
                return
            user_uuid = user.get("uuid")
        except Exception as ex:
            logger.error(f"User lookup failed: {ex}")
            await call.message.edit_text("⚠️ Account lookup failed. Please try again later.")
            await state.clear()
            return

        # Step 2: Check wallet
        try:
            wallet = await WalletService.get_wallet_for_user(telegram_id)
            if not wallet:
                await call.message.edit_text("🚫 No wallet found. Please contact support to set up your wallet.")
                await state.clear()
                return
        except Exception as ex:
            logger.error(f"Wallet lookup failed: {ex}")
            await call.message.edit_text("⚠️ Wallet check failed. Please try again later.")
            await state.clear()
            return

        # Step 3: Check balance
        price_per_gram = current_price if target_price is None else target_price
        total_price = grams * price_per_gram
        if wallet.get("balance", 0) < total_price:
            logger.info(f"Insufficient balance for user {user_uuid}: required {total_price}, available {wallet.get('balance', 0)}")
            await call.message.edit_text("❌ Insufficient wallet balance. Please top up and try again.")
            await state.clear()
            return

        # Step 4: Create buy order
        try:
            if target_price is None:
                logger.info(f"Creating immediate buy order for user {telegram_id}")
                txn = await BuyService.create_buy_order_for_linked_user(telegram_id, grams)
                if not txn:
                    raise RuntimeError("Failed to create buy order")
                msg = (
                    f"✅ Buy order executed immediately!\n"
                    f"Quantity: {grams}g\n"
                    f"Price per gram: ${current_price:.2f}\n"
                    f"Total price: ${total_price:.2f}\n"
                    f"Order ID: {txn['uuid']}"
                )
            else:
                txn = await BuyService.create_buy_order_for_linked_user(telegram_id, grams, custom_price=target_price)
                if not txn:
                    raise RuntimeError("Failed to create pending buy order")
                msg = (
                    f"✅ Buy order is pending.\n"
                    f"Quantity: {grams}g\n"
                    f"Target price per gram: ${target_price:.2f}\n"
                    "You'll be notified when it executes."
                )
        except RuntimeError as ex:
            logger.error(f"BuyService error for user {telegram_id}: {ex}")
            await call.message.edit_text("⚠️ Could not place your order at this time. Please try again.")
            await state.clear()
            return
        except Exception as ex:
            logger.error(f"Order creation unexpected error for user {telegram_id}: {ex}")
            await call.message.edit_text("⚠️ An unexpected error occurred while placing order. Please try again later.")
            await state.clear()
            return

        # Step 5: Deduct funds
        try:
            wallet_deducted = await WalletService.deduct_wallet_balance(user_uuid, total_price)
            if not wallet_deducted:
                await call.message.edit_text("❌ Insufficient wallet balance. Please top up and try again.")
                await state.clear()
                return
        except Exception as ex:
            logger.error(f"Wallet deduction failed for user {telegram_id}: {ex}")
            await call.message.edit_text("⚠️ Wallet deduction failed. Please try again.")
            await state.clear()
            return

        # Success
        await call.message.edit_text(msg)

    except Exception as e:
        logger.error(f"Buy order critical failure for user {telegram_id}: {e}")
        await call.message.edit_text("⚠️ An unexpected error occurred. Please try again later.")

    await state.clear()
    await call.answer()


@router.callback_query(F.data == "cancel")
async def cancel_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ Operation cancelled.")
    await state.clear()
    await call.answer()  # This is important to stop the loading spinner
    logger.info(f"User {call.from_user.id} cancelled the operation.")