import time
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.state import StateFilter
from app.services.telegram.telegram_service import TelegramService
from app.services.user.user_service import UserService
from app.utils.common import format_timestamp
from app.utils.config import settings
from app.utils.logging import get_logger
from app.db.mongo.helper import MongoHelper

router = Router()
logger = get_logger(__name__)

class TransactionsStates(StatesGroup):
    waiting_page = State()

ITEMS_PER_PAGE = 5

# New function to build the time range selection keyboard
def build_time_range_keyboard() -> types.InlineKeyboardMarkup:
    buttons = [
        types.InlineKeyboardButton(text="Today", callback_data="tx_time_today"),
        types.InlineKeyboardButton(text="Yesterday", callback_data="tx_time_yesterday"),
        types.InlineKeyboardButton(text="Last Week", callback_data="tx_time_lastweek"),
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard

@router.message(lambda m: (m.text or "").strip().lower() == "transactions")
async def transactions_start(message: types.Message, state: FSMContext):
    logger.info(f"[transactions_list] User {message.from_user.id} requested transactions time filter")
    if not await UserService.ensure_user_approved(message):
        return
    user = await TelegramService.get_link_for_telegram(message.from_user.id)
    if not user:
        await message.answer("⚠️ User not found. Please contact support.")
        return

    await state.update_data(user_uuid=user.get("uuid"))
    await state.set_state(TransactionsStates.waiting_page)  # Or another state if needed for time filter

    keyboard = build_time_range_keyboard()
    await message.answer("Select the time range for transactions:", reply_markup=keyboard)


# New callback to handle time range selection
@router.callback_query(F.data.startswith("tx_time_"), StateFilter(TransactionsStates.waiting_page))
async def transactions_time_filter(callback: types.CallbackQuery, state: FSMContext):
    time_filter = callback.data.split("_")[-1]
    data = await state.get_data()
    user_uuid = data.get("user_uuid")
    if not user_uuid:
        await callback.answer("Session expired, please try 'transactions' again.", show_alert=True)
        await state.clear()
        return

    now_ts = int(time.time())
    # Calculate start and end timestamps based on selection
    if time_filter == "today":
        # start of today in UTC
        start_ts = int(time.mktime(time.gmtime(time.time() // 86400 * 86400)))
        end_ts = start_ts + 86400
    elif time_filter == "yesterday":
        start_ts = int(time.mktime(time.gmtime((time.time() // 86400 - 1) * 86400)))
        end_ts = start_ts + 86400
    elif time_filter == "lastweek":
        start_ts = now_ts - 7 * 86400
        end_ts = now_ts
    else:
        await callback.answer("Invalid selection.", show_alert=True)
        return

    query = {
        "user_id": user_uuid,
        "updated_at": {"$gte": start_ts, "$lt": end_ts}
    }

    transactions = await MongoHelper.find_many(
        collection=settings.DB_TABLE.TRANSACTIONS,
        query=query,
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
    total_count = await MongoHelper.count_documents("transactions", query)

    if not transactions:
        await callback.message.edit_text(f"No transactions found for selected period: {time_filter.capitalize()}.")
        await callback.answer()
        return

    lines = [f"📜 Your Transactions ({time_filter.capitalize()}), Page 1/{(total_count + ITEMS_PER_PAGE - 1)//ITEMS_PER_PAGE}:"]
    for i, tx in enumerate(transactions, start=1):
        line = format_tx_summary(tx, i)
        lines.append(line)

    keyboard = build_pagination_keyboard(1, total_count)

    await callback.message.edit_text("\n".join(lines), reply_markup=keyboard)
    await state.update_data(page=1, time_filter=time_filter)
    await callback.answer()


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
    updated_at_str = format_timestamp(updated_at) if updated_at else "N/A"
    
    return (
        f"{idx}. {tx_type} | Status: {status}\n"
        f"   Buy: {buy_grams}g @ ${buy_price:.2f} ({buy_price_type})\n"
        f"   Sell: {sell_grams}g @ ${sell_price:.2f} ({sell_price_type})\n"
        f"   PnL: ${pnl_str} | ID: {tx.get('uuid')[:8]}\n"
        f"   Updated At: {updated_at_str}\n"
        f"------------------------"
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

