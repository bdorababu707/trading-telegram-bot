# from aiogram import Router
# from aiogram.types import Message
# from aiogram.fsm.context import FSMContext
# from app.telegram.keyboards import MAIN_MENU
# from app.services.telegram.telegram_service import TelegramService
# from app.services.user.user_service import UserService
# from app.services.wallet.wallet_service import WalletService
# from app.utils.logging import get_logger

# router = Router()

# logger = get_logger(__name__)

# @router.message()
# async def main_handler(message: Message, state: FSMContext):
#     # prior state check logic
#     text = message.text
#     if text.lower() in ["/start", "hi", "hello", "menu"]:
#         user = await UserService.create_telegram_user(
#             telegram_id=message.from_user.id,
#             username=message.from_user.username,
#             first_name=message.from_user.first_name,
#             last_name=message.from_user.last_name
#         )
#         logger.info("User ensured: %s", user.get("uuid"))

#         # Create wallet if it does not exist
#         wallet = await WalletService.create_wallet_for_user(user.get("uuid"))

#         await message.answer(
#             "Welcome to Gold Trading Bot! 💰",
#             reply_markup=MAIN_MENU,
#         )
#         return


#     # Do NOT handle "buy gold" here, let FSM buy handler catch it

#     # if "sell gold" in text:
#     #     await message.answer("➡️ You selected *Sell*", parse_mode="Markdown")
#     if "live price" in text:
#         await message.answer("📈 Current gold price is ...")
#     elif "positions" in text or "open positions" in text:
#         await message.answer("📂 Your open positions are ...")
#     elif "close position" in text:
#         await message.answer("❌ Select a position to close ...")
#     elif "transactions" in text:
#         await message.answer("🧾 Here are your past transactions ...")
#     else:
#         await message.answer("❓ Sorry, I did not understand that. Please send one of these messages: /start, hi, hello, menu.")


from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.services.user.user_service import UserService
from app.services.wallet.wallet_service import WalletService
from app.telegram.keyboards import MAIN_MENU
from app.utils.logging import get_logger
import re

router = Router()
logger = get_logger(__name__)

phone_pattern = re.compile(r'^\+[1-9][0-9]{6,14}$')

class RegistrationStates(StatesGroup):
    waiting_for_phone = State()

MAX_PHONE_ATTEMPTS = 3

@router.message()
async def handle_message(message: Message, state: FSMContext):
    user = await UserService.get_user_by_telegram_id(message.from_user.id)

    if user:
        # Existing user
        status = user.get("status")
        if status == "PENDING":
            await message.answer("Your account activation is in progress. Please wait for approval.")
            return
        elif status == "APPROVED":
            await process_user_command(message)
            return

    # New user or no record found
    current_state = await state.get_state()
    if current_state == RegistrationStates.waiting_for_phone.state:
        # Get or increment attempts counter
        data = await state.get_data()
        wrong_attempts = data.get("wrong_phone_attempts", 0)
        phone = (message.text or "").strip()
        if not phone_pattern.match(phone):
            wrong_attempts += 1
            await state.update_data(wrong_phone_attempts=wrong_attempts)
            if wrong_attempts >= MAX_PHONE_ATTEMPTS:
                await message.answer(
                    "❌ Too many invalid phone number attempts. "
                    "Session expired. Please send /start or hi to try again."
                )
                await state.clear()
                return
            await message.answer(
                f"Please send a valid phone number with country code. (Attempt {wrong_attempts}/{MAX_PHONE_ATTEMPTS})"
            )
            return

        # PHONE NUMBER DUPLICATION CHECK 
        existing_user = await UserService.get_user_by_phone_number(phone)
        if existing_user:
            wrong_attempts += 1
            await state.update_data(wrong_phone_attempts=wrong_attempts)
            await message.answer(
                f"This mobile number is already registered. Please enter a different one. (Attempt {wrong_attempts}/{MAX_PHONE_ATTEMPTS})"
            )
            if wrong_attempts >= MAX_PHONE_ATTEMPTS:
                await message.answer("❌ Too many invalid attempts. Session expired. Please send /start or hi to try again.")
                await state.clear()
            return

        # if phone is valid and not duplicate, continue with registration
        # Reset attempt counter (valid input)
        await state.update_data(wrong_phone_attempts=0)

        # Create user with PENDING status
        user = await UserService.create_telegram_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            phone_number=phone,
            status="PENDING"
        )
        wallet = await WalletService.create_wallet_for_user(user.get("uuid"))
        logger.info("Created wallet for user %s", user.get("uuid"))

        await message.answer("Thank you for registering! We will process your account activation shortly.")
        await state.clear()
        return

    # If not waiting for phone, prompt user to send phone number
    await message.answer("Welcome! Please send your mobile number with country code to register (eg: +1234567890).")
    await state.set_state(RegistrationStates.waiting_for_phone)

async def process_user_command(message: Message):
    text = (message.text or "").lower()
    if text in ["/start", "hi", "hello", "menu"]:
        # Approved user asks for menu: show all main features/buttons
        await message.answer(
            "Welcome to Gold Trading Bot! 💰\nSelect an option:",
            reply_markup=MAIN_MENU  # Use your keyboard layout that shows Buy/Sell/Wallet/etc.
        )
    elif "live price" in text:
        await message.answer("📈 Current gold price is ...")
    elif "positions" in text or "open positions" in text:
        await message.answer("📂 Your open positions are ...")
    # Add further elif blocks for buy, sell, wallet, etc. here!
    else:
        await message.answer("Unknown command. Please send one of the following commands: /start, hi, hello, menu.")

