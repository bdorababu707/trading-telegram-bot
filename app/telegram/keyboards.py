from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# MAIN_MENU = ReplyKeyboardMarkup(
#     keyboard=[
#         [KeyboardButton("💰 Buy Gold"), KeyboardButton("📉 Sell Gold")],
#         [KeyboardButton("📊 Live Price"), KeyboardButton("📂 Open Positions")],
#         [KeyboardButton("❌ Close Position"), KeyboardButton("/link <CODE>")],
#         [KeyboardButton("🧾 Transactions")]
#     ],
#     resize_keyboard=True
# )

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Buy Gold"), KeyboardButton(text="Sell Gold")],
        [KeyboardButton(text="Live Price"), KeyboardButton(text="Wallet")],
        [KeyboardButton(text="Open Positions"), KeyboardButton(text="Closed Positions")], 
        [KeyboardButton(text="Transactions")],
    ],
    resize_keyboard=True
)


def confirm_inline(action: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Confirm {action}", callback_data=f"confirm:{action}"
                )
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
        ]
    )

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def positions_kb(positions: list, current_price: float = None) -> InlineKeyboardMarkup:
    inline_keyboard = []

    for p in positions:
        buy_grams = p.get("buy_grams") or 0
        buy_price = p.get("buy_price") or 0
        sell_grams = p.get("sell_grams") or 0
        sell_price = p.get("sell_price")

        # Calculate PNL
        if sell_price is not None and sell_grams > 0:
            # Realized PNL
            pnl = (sell_price - buy_price) * sell_grams
        elif current_price is not None:
            # Unrealized PNL based on current price and buy grams
            pnl = (current_price - buy_price) * buy_grams
        else:
            pnl = 0

        pnl_text = f"{pnl:+.2f}"  # Show with + or - and two decimals
        current_price_text = f"${current_price:.2f}" if current_price is not None else "N/A"

        text = (
            f"Buy: {buy_grams}g | Open: ${buy_price:.2f} | "
            f"Current: {current_price_text} | PNL: {pnl_text}"
        )
        callback_data = f"pos:{p['uuid']}"
        inline_keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    # Add Back button
    inline_keyboard.append([InlineKeyboardButton(text="⬅ Back", callback_data="menu")])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# def positions_kb(positions: list, current_price: float = None) -> InlineKeyboardMarkup:
#     inline_keyboard = []

#     for p in positions:
#         buy_grams = p.get("buy_grams") or 0
#         buy_price = p.get("buy_price") or 0
#         sell_grams = p.get("sell_grams") or 0
#         sell_price = p.get("sell_price")

#         # Calculate PNL
#         if sell_price is not None and sell_grams > 0:
#             # Realized PNL
#             pnl = (sell_price - buy_price) * sell_grams
#         elif current_price is not None:
#             # Unrealized PNL based on current price and buy grams
#             pnl = (current_price - buy_price) * buy_grams
#         else:
#             pnl = 0

#         pnl_text = f"{pnl:+.2f}"  # Show with + or - and two decimals

#         text = f"PNL: {pnl_text} | {buy_grams}g"
#         callback_data = f"pos:{p['uuid']}"
#         inline_keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

#     # Add Back button
#     inline_keyboard.append([InlineKeyboardButton(text="⬅ Back", callback_data="menu")])

#     return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
