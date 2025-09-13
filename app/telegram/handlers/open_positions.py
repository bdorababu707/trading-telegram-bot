import time
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.services.telegram.telegram_service import TelegramService
from app.services.positions.position_service import PositionService
from app.db.mongo.helper import MongoHelper
from app.services.user.user_service import UserService
from app.utils.common import check_retry_limit
from app.utils.config import settings
from app.services.price.price_service import get_current_price
from app.utils.logging import get_logger


import time
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.services.telegram.telegram_service import TelegramService
from app.utils.logging import get_logger
from app.db.mongo.helper import MongoHelper
from app.telegram.keyboards import confirm_inline

router = Router()
logger = get_logger(__name__)

class ClosePositionStates(StatesGroup):
    waiting_selection = State()
    waiting_confirmation = State()

@router.message(lambda m: (m.text or "").strip().lower() == "open positions")
async def positions_list(message: types.Message, state: FSMContext):
    if not await UserService.ensure_user_approved(message):
        return
    logger.info(f"[positions_list] User {message.from_user.id} requested open positions")
    user = await TelegramService.get_link_for_telegram(message.from_user.id)
    if not user:
        await message.answer("⚠️ User not found. Please contact support.")
        return

    user_uuid = user.get("uuid")
    positions = await MongoHelper.find_many(
        collection="transactions",
        query={"user_id": user_uuid, "status": "OPEN"},
        projection={
            "uuid": 1,
            "buy_at": 1,
            "buy_grams": 1,
            "buy_price": 1,
            "sell_at": 1,
            "sell_grams": 1,
            "sell_price": 1,
        }
    )

    if not positions:
        await message.answer("You have no open positions currently.")
        return

    lines = ["🔓 Your Open Positions:"]
    for i, pos in enumerate(positions, start=1):
        if pos.get("buy_price", 0) > 0:
            lines.append(f"{i}. BUY {pos.get('buy_grams', 0)}g @ ${pos.get('buy_price', 0):.2f} (ID:{pos.get('uuid')[:8]})")
        elif pos.get("sell_price", 0) > 0:
            lines.append(f"{i}. SELL {pos.get('sell_grams', 0)}g @ ${pos.get('sell_price', 0):.2f} (ID:{pos.get('uuid')[:8]})")
        else:
            lines.append(f"{i}. Position ID: {pos.get('uuid')[:8]} (Unknown type)")

    await message.answer("\n".join(lines) + "\n\nSend the number of the position you want to close (e.g., 1) or send 0 to cancel:")
    await state.update_data(positions=positions)
    await state.set_state(ClosePositionStates.waiting_selection)

@router.message(ClosePositionStates.waiting_selection)
async def position_selection(message: types.Message, state: FSMContext):
    logger.info(f"[position_selection] User {message.from_user.id} selection: {message.text}")
    text = message.text.strip().lower()
    
    if text == "0":
        await message.answer("❌ Operation cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    positions = data.get("positions", [])

    if not text.isdigit():
        can_continue = await check_retry_limit(
            message,
            state,
            attempt_key="wrong_position_attempts",
            error_text="❌ Please enter a valid position number.",
            expired_text="❌ Too many invalid attempts! Session expired. Please type 'open positions' to restart."
        )
        if not can_continue:
            return
        else:
            return

    idx = int(text)
    if idx < 1 or idx > len(positions):
        can_continue = await check_retry_limit(
            message,
            state,
            attempt_key="wrong_position_attempts",
            error_text="❌ Number out of range. Please try again.",
            expired_text="❌ Too many invalid attempts! Session expired. Please type 'open positions' to restart."
        )
        if not can_continue:
            return
        return

    # Valid selection — reset counter
    await state.update_data(wrong_position_attempts=0)
    selected_pos = positions[idx - 1]
    await state.update_data(selected_pos=selected_pos)
    logger.info(f"[position_selection] User {message.from_user.id} selected position {selected_pos.get('uuid')}")

    # Fetch current price for confirmation
    try:
        current_price = await get_current_price()
        await state.update_data(current_price=current_price)
    except Exception as e:
        logger.error(f"[position_selection] Failed to fetch current price: {e}")
        await message.answer("⚠️ Failed to fetch current price. Please try again later.")
        await state.clear()
        return

    # Prepare confirmation message with estimated pnl
    is_buy = selected_pos.get("buy_price", 0) > 0
    buy_price = selected_pos.get("buy_price", 0)
    buy_grams = selected_pos.get("buy_grams", 0)
    sell_price = selected_pos.get("sell_price", 0)
    sell_grams = selected_pos.get("sell_grams", 0)

    pnl = 0
    if is_buy:
        pnl = (current_price * buy_grams) - (buy_price * buy_grams)
        position_desc = f"BUY {buy_grams}g @ ${buy_price:.2f}"
    else:
        pnl = (sell_price * sell_grams) - (current_price * sell_grams)
        position_desc = f"SELL {sell_grams}g @ ${sell_price:.2f}"

    confirm_text = (
        f"Confirm closing this position:\n\n"
        f"{position_desc}\n"
        f"Closing at current price: ${current_price:.2f}\n"
        f"Estimated PnL: ${pnl:.2f}\n\n"
        "Reply with '1' to confirm or '0' to cancel."
    )
    await message.answer(confirm_text)
    await state.set_state(ClosePositionStates.waiting_confirmation)


@router.message(ClosePositionStates.waiting_confirmation)
async def confirm_close(message: types.Message, state: FSMContext):
    logger.info(f"[confirm_close] User {message.from_user.id} reply: {message.text}")
    text = message.text.strip().lower()

    # Handle cancel explicitly
    if text == "0":
        await message.answer("❌ Operation cancelled.")
        await state.clear()
        return

    # Validate input; only "0" (cancel) and "1" (confirm) allowed
    if text not in ("0", "1"):
        can_continue = await check_retry_limit(
            message,
            state,
            attempt_key="wrong_confirmation_attempts",
            error_text="⚠️ Please reply with '1' to confirm or '0' to cancel.",
            expired_text="❌ Too many invalid attempts! Session expired. Please start over."
        )
        if not can_continue:
            return
        else:
            return

    # If confirm ("1"), reset retry counter and continue closing logic
    await state.update_data(wrong_confirmation_attempts=0)

    if text == "1":
        # Retrieve necessary data
        data = await state.get_data()
        selected_pos = data.get("selected_pos")
        current_price = data.get("current_price")
        telegram_id = message.from_user.id

        if not (selected_pos and current_price):
            await message.answer("⚠️ Missing position or price data. Please start over.")
            await state.clear()
            return

        user = await TelegramService.get_link_for_telegram(telegram_id)
        if not user:
            await message.answer("⚠️ User not found. Please contact support.")
            await state.clear()
            return
        user_uuid = user.get("uuid")

        # Prepare rollback info
        rollback_fields = {k: selected_pos.get(k, None) for k in [
            "buy_at", "buy_grams", "buy_price", "buy_price_type", "total_buy_amount",
            "sell_at", "sell_grams", "sell_price", "sell_price_type", "total_sell_amount",
            "status", "pnl", "updated_at"
        ]}

        try:
            is_buy = selected_pos.get("buy_price", 0) > 0
            buy_grams = selected_pos.get("buy_grams", 0)
            buy_price = selected_pos.get("buy_price", 0)
            sell_grams = selected_pos.get("sell_grams", 0)
            sell_price = selected_pos.get("sell_price", 0)

            now_ts = int(time.time())
            if is_buy:
                pnl = (current_price * buy_grams) - (buy_price * buy_grams)
                update = {
                    "$set": {
                        "sell_at": now_ts,
                        "sell_grams": buy_grams,
                        "sell_price": current_price,
                        "sell_price_type": "MARKET",
                        "total_sell_amount": current_price * buy_grams,
                        "status": "CLOSED",
                        "pnl": pnl,
                        "updated_at": now_ts
                    }
                }
                credit_amount = (buy_price * buy_grams) + pnl
            else:
                pnl = (sell_price * sell_grams) - (current_price * sell_grams)
                update = {
                    "$set": {
                        "buy_at": now_ts,
                        "buy_grams": sell_grams,
                        "buy_price": current_price,
                        "buy_price_type": "MARKET",
                        "total_buy_amount": current_price * sell_grams,
                        "status": "CLOSED",
                        "pnl": pnl,
                        "updated_at": now_ts
                    }
                }
                credit_amount = (sell_price * sell_grams) + pnl

            txn_affected = await MongoHelper.update_one(
                collection=settings.DB_TABLE.TRANSACTIONS,
                query={"uuid": selected_pos.get("uuid")},
                update=update
            )
            if txn_affected == 0:
                raise RuntimeError("Failed to update transaction status")

            wallet = await MongoHelper.find_one(settings.DB_TABLE.WALLETS, {"user_id": user_uuid})
            if not wallet:
                # rollback
                await MongoHelper.update_one(
                    collection="transactions",
                    query={"uuid": selected_pos.get("uuid")},
                    update={"$set": rollback_fields}
                )
                await message.answer("⚠️ Wallet not found. Operation aborted and rolled back.")
                await state.clear()
                return

            wallet_affected = await MongoHelper.update_one(
                collection=settings.DB_TABLE.WALLETS,
                query={"user_id": user_uuid},
                update={"$inc": {"balance": credit_amount}}
            )
            if wallet_affected == 0:
                await MongoHelper.update_one(
                    collection="transactions",
                    query={"uuid": selected_pos.get("uuid")},
                    update={"$set": rollback_fields}
                )
                raise RuntimeError("Failed to update wallet balance; rolled back transaction")

            updated_wallet = await MongoHelper.find_one(settings.DB_TABLE.WALLETS, {"user_id": user_uuid})
            if not updated_wallet:
                raise RuntimeError("Updated wallet missing after balance increment")
            new_balance = updated_wallet.get("balance", 0)

            await message.answer(
                f"✅ Position closed successfully!\n"
                f"PnL Realized: ${pnl:.2f}\n"
                f"Updated Wallet Balance: ${new_balance:.2f}"
            )
        except Exception as e:
            logger.error(f"Error closing position for user {user_uuid}: {e}")
            await message.answer("❌ Failed to close position due to internal error. Please try again later.")
        finally:
            await state.clear()

# @router.message(ClosePositionStates.waiting_confirmation)
# async def confirm_close(message: types.Message, state: FSMContext):
#     logger.info(f"[confirm_close] User {message.from_user.id} reply: {message.text}")
#     text = message.text.strip().lower()

#     if text == "0":
#         await message.answer("❌ Operation cancelled.")
#         await state.clear()
#         return

#     if text not in ("0", "1"):
#         can_continue = await check_retry_limit(
#             message,
#             state,
#             attempt_key="wrong_confirmation_attempts",
#             error_text="⚠️ Please reply with '1' to confirm or '0' to cancel.",
#             expired_text="❌ Too many invalid attempts! Session expired. Please start over."
#         )
#         if not can_continue:
#             return
#         else:
#             return

#     if text == "no":
#         await message.answer("❌ Closing canceled.")
#         await state.clear()
#         return

#     # Reset confirmation attempts on valid input
#     await state.update_data(wrong_confirmation_attempts=0)

#     # Continue with closing logic...

#     data = await state.get_data()
#     selected_pos = data.get("selected_pos")
#     current_price = data.get("current_price")
#     telegram_id = message.from_user.id

#     if not (selected_pos and current_price):
#         await message.answer("⚠️ Missing position or price data. Please start over.")
#         await state.clear()
#         return

#     user = await TelegramService.get_link_for_telegram(telegram_id)
#     if not user:
#         await message.answer("⚠️ User not found. Please contact support.")
#         await state.clear()
#         return
#     user_uuid = user.get("uuid")

#     # Prepare rollback info
#     rollback_fields = {k: selected_pos.get(k, None) for k in [
#         "buy_at","buy_grams","buy_price","buy_price_type","total_buy_amount",
#         "sell_at","sell_grams","sell_price","sell_price_type","total_sell_amount",
#         "status","pnl","updated_at"
#     ]}

#     try:
#         is_buy = selected_pos.get("buy_price", 0) > 0
#         buy_grams = selected_pos.get("buy_grams", 0)
#         buy_price = selected_pos.get("buy_price", 0)
#         sell_grams = selected_pos.get("sell_grams", 0)
#         sell_price = selected_pos.get("sell_price", 0)

#         now_ts = int(time.time())
#         if is_buy:
#             pnl = (current_price * buy_grams) - (buy_price * buy_grams)
#             update = {
#                 "$set": {
#                     "sell_at": now_ts,
#                     "sell_grams": buy_grams,
#                     "sell_price": current_price,
#                     "sell_price_type": "MARKET",
#                     "total_sell_amount": current_price * buy_grams,
#                     "status": "CLOSED",
#                     "pnl": pnl,
#                     "updated_at": now_ts
#                 }
#             }
#             credit_amount = (buy_price * buy_grams) + pnl
#         else:
#             pnl = (sell_price * sell_grams) - (current_price * sell_grams)
#             update = {
#                 "$set": {
#                     "buy_at": now_ts,
#                     "buy_grams": sell_grams,
#                     "buy_price": current_price,
#                     "buy_price_type": "MARKET",
#                     "total_buy_amount": current_price * sell_grams,
#                     "status": "CLOSED",
#                     "pnl": pnl,
#                     "updated_at": now_ts
#                 }
#             }
#             credit_amount = (sell_price * sell_grams) + pnl

#         txn_affected = await MongoHelper.update_one(
#             collection=settings.DB_TABLE.TRANSACTIONS,
#             query={"uuid": selected_pos.get("uuid")},
#             update=update
#         )
#         if txn_affected == 0:
#             raise RuntimeError("Failed to update transaction status")

#         wallet = await MongoHelper.find_one(settings.DB_TABLE.WALLETS, {"user_id": user_uuid})
#         if not wallet:
#             # rollback
#             await MongoHelper.update_one(
#                 collection="transactions",
#                 query={"uuid": selected_pos.get("uuid")},
#                 update={"$set": rollback_fields}
#             )
#             await message.answer("⚠️ Wallet not found. Operation aborted and rolled back.")
#             await state.clear()
#             return

#         wallet_affected = await MongoHelper.update_one(
#             collection=settings.DB_TABLE.WALLETS,
#             query={"user_id": user_uuid},
#             update={"$inc": {"balance": credit_amount}}
#         )
#         if wallet_affected == 0:
#             await MongoHelper.update_one(
#                 collection="transactions",
#                 query={"uuid": selected_pos.get("uuid")},
#                 update={"$set": rollback_fields}
#             )
#             raise RuntimeError("Failed to update wallet balance; rolled back transaction")

#         updated_wallet = await MongoHelper.find_one(settings.DB_TABLE.WALLETS, {"user_id": user_uuid})
#         if not updated_wallet:
#             raise RuntimeError("Updated wallet missing after balance increment")
#         new_balance = updated_wallet.get("balance", 0)

#         await message.answer(
#             f"✅ Position closed successfully!\n"
#             f"PnL Realized: ${pnl:.2f}\n"
#             f"Updated Wallet Balance: ${new_balance:.2f}"
#         )
#     except Exception as e:
#         logger.error(f"Error closing position for user {user_uuid}: {e}")
#         await message.answer("❌ Failed to close position due to internal error. Please try again later.")
#     finally:
#         await state.clear()
