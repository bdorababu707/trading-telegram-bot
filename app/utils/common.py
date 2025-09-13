import uuid

async def generate_uuid() -> str:
    return str(uuid.uuid4())

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
from functools import wraps
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

INACTIVITY_TIMEOUT = 60  # 1 minute

from time import time

def inactivity_timeout_guard(attempt_key: str = "last_active", timeout: int = 60):
    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, state: FSMContext, *args, **kwargs):
            data = await state.get_data()
            last_active = data.get(attempt_key)
            now = int(time())
            if last_active is not None:
                if now - last_active > timeout:
                    await state.clear()
                    await message.answer("❌ Session expired due to inactivity. Please start again.")
                    return
            # Update last_active timestamp for all cases (including first-time)
            await state.update_data(**{attempt_key: now})
            return await func(message, state, *args, **kwargs)
        return wrapper
    return decorator
