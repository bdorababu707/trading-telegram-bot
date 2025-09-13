from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from enum import Enum


class TxStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"


class Transaction(BaseModel):
    uuid: str 
    user_id: str
    buy_at: Optional[int] = None
    buy_grams: Optional[float] = None
    buy_price: Optional[float] = None
    buy_price_type: Optional[str] = None  # Made Optional to accept None
    total_buy_amount: Optional[float] = None
    sell_at: Optional[int] = None
    sell_grams: Optional[float] = None
    sell_price: Optional[float] = None
    sell_price_type: Optional[str] = None
    total_sell_amount: Optional[float] = None
    status: TxStatus = TxStatus.OPEN
    pnl: Optional[float] = 0  # Profit and Loss, can be calculated later
    updated_at: Optional[int] = None  # Timestamp of last update