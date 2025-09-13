from functools import wraps
from aiogram import types
from app.utils.logging import get_logger

logger = get_logger(__name__)

def handle_bot_errors(user_friendly_message: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(message_or_call, *args, **kwargs):
            try:
                return await func(message_or_call, *args, **kwargs)
            except Exception as e:
                user_id = None
                if hasattr(message_or_call, 'from_user') and message_or_call.from_user:
                    user_id = message_or_call.from_user.id
                elif hasattr(message_or_call, 'chat') and message_or_call.chat:
                    user_id = message_or_call.chat.id

                logger.error(f"Error in handler {func.__name__} for user {user_id}: {e}")

                if isinstance(message_or_call, types.Message):
                    await message_or_call.answer(user_friendly_message)
                elif hasattr(message_or_call, 'message'):
                    await message_or_call.message.answer(user_friendly_message)
                    await message_or_call.answer()

        return wrapper
    return decorator
