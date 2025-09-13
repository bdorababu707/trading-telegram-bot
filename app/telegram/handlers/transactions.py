import time
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.state import StateFilter
from app.services.telegram.telegram_service import TelegramService
from app.services.user.user_service import UserService
from app.utils.config import settings
from app.utils.logging import get_logger
from app.db.mongo.helper import MongoHelper


router = Router()
logger = get_logger(__name__)


class TransactionsStates(StatesGroup):
    waiting_page = State()


ITEMS_PER_PAGE = 5


@router.message(lambda m: (m.text or "").strip().lower() == "transactions")
async def transactions_list(message: types.Message, state: FSMContext):
    logger.info(f"[transactions_list] User {message.from_user.id} requested all transactions")
    if not await UserService.ensure_user_approved(message):
        return
    user = await TelegramService.get_link_for_telegram(message.from_user.id)
    if not user:
        await message.answer("⚠️ User not found. Please contact support.")
        return

    user_uuid = user.get("uuid")

    transactions = await MongoHelper.find_many(
        collection="transactions",
        query={"user_id": user_uuid},
        sort=[("updated_at", -1)],
        limit=ITEMS_PER_PAGE,
        skip=0,
        projection={
            "uuid": 1,
            "buy_at": 1,
            "buy_grams": 1,
            "buy_price": 1,
            "buy_price_type": 1,
            "sell_at": 1,
            "sell_grams": 1,
            "sell_price": 1,
            "sell_price_type": 1,
            "status": 1,
            "pnl": 1,
            "updated_at": 1,
        }
    )

    total_count = await MongoHelper.count_documents(settings.DB_TABLE.TRANSACTIONS, {"user_id": user_uuid})

    if not transactions:
        await message.answer("You have no transactions currently.")
        return

    lines = [f"📜 Your Transactions (Page 1/{(total_count + ITEMS_PER_PAGE - 1)//ITEMS_PER_PAGE}):"]
    for i, tx in enumerate(transactions, start=1):
        line = format_tx_summary(tx, i)
        lines.append(line)

    keyboard = build_pagination_keyboard(1, total_count)

    await message.answer("\n".join(lines), reply_markup=keyboard)
    await state.update_data(user_uuid=user_uuid, page=1)
    await state.set_state(TransactionsStates.waiting_page)


@router.callback_query(F.data.startswith('tx_page_'), StateFilter(TransactionsStates.waiting_page))
async def transactions_pagination(callback: types.CallbackQuery, state: FSMContext):
    page_str = callback.data.split('_')[-1]
    if not page_str.isdigit():
        await callback.answer("Invalid page number.", show_alert=True)
        return
    page = int(page_str)

    data = await state.get_data()
    print(data)
    user_uuid = data.get("user_uuid")
    if not user_uuid:
        await callback.answer("Session expired, please try /transactions again.", show_alert=True)
        await state.clear()
        return

    skip = (page - 1) * ITEMS_PER_PAGE
    total_count = await MongoHelper.count_documents(settings.DB_TABLE.TRANSACTIONS, {"user_id": user_uuid})

    transactions = await MongoHelper.find_many(
        collection=settings.DB_TABLE.TRANSACTIONS,
        query={"user_id": user_uuid},
        sort=[("updated_at", -1)],
        limit=ITEMS_PER_PAGE,
        skip=skip,
        projection={
            "uuid": 1,
            "buy_at": 1,
            "buy_grams": 1,
            "buy_price": 1,
            "buy_price_type": 1,
            "sell_at": 1,
            "sell_grams": 1,
            "sell_price": 1,
            "sell_price_type": 1,
            "status": 1,
            "pnl": 1,
            "updated_at": 1,
        }
    )

    if not transactions:
        await callback.answer("No transactions on this page.", show_alert=True)
        return

    lines = [f"📜 Your Transactions (Page {page}/{(total_count + ITEMS_PER_PAGE - 1)//ITEMS_PER_PAGE}):"]
    for i, tx in enumerate(transactions, start=skip+1):
        line = format_tx_summary(tx, i)
        lines.append(line)

    keyboard = build_pagination_keyboard(page, total_count)

    await callback.message.edit_text("\n".join(lines), reply_markup=keyboard)
    await callback.answer()
    await state.update_data(page=page)


def format_tx_summary(tx: dict, idx: int) -> str:
    is_buy = tx.get("buy_grams", 0) > 0
    is_sell = tx.get("sell_grams", 0) > 0
    tx_type = "BUY" if is_buy and not is_sell else "SELL" if is_sell and not is_buy else "MIXED"
    pnl = tx.get("pnl", 0)
    pnl_str = f"{pnl:.2f}"
    buy_grams = tx.get("buy_grams", 0)
    buy_price = tx.get("buy_price", 0)
    buy_price_type = tx.get("buy_price_type") or ""
    sell_grams = tx.get("sell_grams", 0)
    sell_price = tx.get("sell_price", 0)
    sell_price_type = tx.get("sell_price_type") or ""
    status = tx.get("status", "N/A").capitalize()
    updated_at = tx.get("updated_at")

    return (
        f"{idx}. {tx_type} | Status: {status}\n"
        f"   Buy: {buy_grams}g @ ${buy_price:.2f} ({buy_price_type})\n"
        f"   Sell: {sell_grams}g @ ${sell_price:.2f} ({sell_price_type})\n"
        f"   PnL: ${pnl_str} | ID: {tx.get('uuid')[:8]} | Updated_at: {updated_at}\n"
    )

def build_pagination_keyboard(current_page: int, total_count: int) -> types.InlineKeyboardMarkup:
    total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    buttons = []
    if current_page > 1:
        buttons.append(types.InlineKeyboardButton(text="⬅ Prev", callback_data=f"tx_page_{current_page-1}"))
    if current_page < total_pages:
        buttons.append(types.InlineKeyboardButton(text="Next ➡", callback_data=f"tx_page_{current_page+1}"))
    
    inline_keyboard = []
    if buttons:
        inline_keyboard.append(buttons)  # a single row
    
    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

