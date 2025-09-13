from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from enum import Enum
import time

class UserLink(BaseModel):
    uuid: str 
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    link_code: Optional[str] = None
    created_at: int 
