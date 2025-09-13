from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.telegram.handlers.start import router as start_router
from app.telegram.handlers.buy import router as buy_router
from app.telegram.handlers.sell import router as sell_router
from app.telegram.handlers.price import router as price_router
from app.telegram.handlers.closed_positions import router as closed_positions_router
from app.telegram.handlers.open_positions import router as open_positions_router
from app.telegram.handlers.transactions import router as transactions_router
from app.telegram.handlers.wallet import router as wallet_router


storage = MemoryStorage() 

def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp.include_router(buy_router)     # Register FSM handler first
    dp.include_router(sell_router)   # Register generic router after
    dp.include_router(price_router)
    dp.include_router(wallet_router)
    dp.include_router(closed_positions_router)
    dp.include_router(open_positions_router)
    dp.include_router(transactions_router)
    dp.include_router(start_router)
    return dp
