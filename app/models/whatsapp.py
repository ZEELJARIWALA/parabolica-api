from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class WhatsappContact(BaseModel):
    phone: str
    name: Optional[str] = "Unknown Pilot"
    last_message: Optional[str] = None
    created_at: Optional[datetime] = None

class WhatsappMessage(BaseModel):
    from_phone: str
    name: str
    text: str
    timestamp: str
