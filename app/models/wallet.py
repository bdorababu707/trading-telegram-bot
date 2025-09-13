from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4

class Wallet(BaseModel):
    uuid: str
    user_id: str  # Reference to user UUID or Telegram ID
    balance: float = 0.0
    status: str = "ACTIVE"
    currency: str = "USD"
    created_at: int
    updated_at: int
