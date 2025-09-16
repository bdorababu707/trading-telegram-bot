import uuid

async def generate_uuid() -> str:
    return str(uuid.uuid4())

from datetime import datetime, timedelta, timezone

def format_timestamp(timestamp: int) -> str:
    ist_offset = timedelta(hours=5, minutes=30)  # IST offset from UTC
    ist_timezone = timezone(ist_offset)
    dt = datetime.fromtimestamp(timestamp, tz=ist_timezone)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

MAX_ATTEMPTS_DEFAULT = 3

async def check_retry_limit(
    message: Message,
    state: FSMContext,
    attempt_key: str,
    max_attempts: int = MAX_ATTEMPTS_DEFAULT,
    error_text: str = "Invalid input, please try again.",
    expired_text: str = "Too many invalid attempts. Session expired. Please start again."
) -> bool:
    """
    Tracks invalid input attempts using FSM state storage.

    Args:
        message: The incoming message.
        state: FSMContext for current conversation.
        attempt_key: Unique key name for this input's wrong attempt counter.
        max_attempts: Maximum allowed invalid attempts.
        error_text: Text to send on non-final invalid attempt.
        expired_text: Text to send upon reaching max attempts.

    Returns:
        True if user still allowed to continue,
        False if limit reached and session should be cleared.
    """
    data = await state.get_data()
    attempts = data.get(attempt_key, 0) + 1
    if attempts >= max_attempts:
        await message.answer(expired_text)
        await state.clear()
        return False
    else:
        await state.update_data({attempt_key: attempts})
        await message.answer(f"{error_text} (Attempt {attempts}/{max_attempts})")
        return True

import time
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.context import FSMContext

INACTIVITY_TIMEOUT = 10  # or 60, as needed

class InactivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        state: FSMContext = data.get("state")
        message_obj = None
        # Identify correct message object for answering
        if isinstance(event, types.Message):
            message_obj = event
        elif isinstance(event, types.CallbackQuery):
            message_obj = event.message

        if state is not None:
            state_data = await state.get_data()
            last_active = state_data.get("last_active")
            now = int(time.time())
            if last_active is not None and now - last_active > INACTIVITY_TIMEOUT:
                await state.clear()
                if message_obj:
                    await message_obj.answer("❌ Session expired due to inactivity. Please start again.")
                return  # Skip handler execution
            # Update last interaction timestamp
            await state.update_data(last_active=now)

        return await handler(event, data)

from functools import wraps
from aiogram import types
from aiogram.fsm.context import FSMContext

def validate_fsm_data_decorator(required_fields: list):
    def decorator(handler_func):
        @wraps(handler_func)
        async def wrapper(event, state, *args, **kwargs):
            message = event.message if hasattr(event, "message") else event
            data = await state.get_data()
            missing_or_none_fields = [f for f in required_fields if data.get(f) is None]

            if missing_or_none_fields:
                await message.answer("❌ Your session expired or required data is missing. Please start again.")
                await state.clear()
                if isinstance(event, types.CallbackQuery):
                    await event.message.edit_reply_markup(reply_markup=None)  # disable buttons
                    await event.answer()  # stop loading spinner
                return  # early return prevents handler execution

            return await handler_func(event, state, *args, **kwargs)

        return wrapper
    return decorator
