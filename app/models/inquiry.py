"""
models/inquiry.py — Pydantic schemas for event inquiry request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional


class CreateInquiryRequest(BaseModel):
    event_type: Literal["BIRTHDAY", "KITTY", "CORPORATE", "WALKTHROUGH"]
    location: Literal["SURAT", "MUMBAI"]
    pilot_name: str = Field(..., min_length=2, max_length=100)
    pilot_email: str = Field(..., min_length=5, max_length=200)
    pilot_phone: str = Field(..., min_length=7, max_length=15)
    message: Optional[str] = Field(None, max_length=1000)

    @field_validator("pilot_email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("A valid email address is required.")
        return v.lower().strip()

    @field_validator("pilot_phone")
    @classmethod
    def phone_must_be_numeric(cls, v: str) -> str:
        cleaned = v.replace("+", "").replace("-", "").replace(" ", "")
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits.")
        return v


class UpdateInquiryStatusRequest(BaseModel):
    status: Literal["NEW", "QUOTED", "CLOSED"]


class InquiryResponse(BaseModel):
    id: str
    user_id: str
    event_type: str
    location: str
    status: str
    message: Optional[str]
    pilot_name: Optional[str] = None
    pilot_phone: Optional[str] = None
    created_at: str
