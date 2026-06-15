"""
models/booking.py — Pydantic schemas for booking-related request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
import datetime


# ─── Game Config Sub-Models ──────────────────────────────────────────────────

class VRConfig(BaseModel):
    players: int = Field(..., ge=1, le=6, description="Number of players (1-6)")
    duration: Literal[30, 45] = Field(..., description="Session duration in minutes")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Time slot e.g. 14:00")
    date: datetime.date = Field(..., description="Mission date (future dates only)")

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime.date) -> datetime.date:
        if v < datetime.date.today():
            raise ValueError("Booking date must be today or in the future.")
        return v


class F1Config(BaseModel):
    type: Literal["FULL", "MOTION", "STATIC"]
    mode: Literal["SOLO", "RACE"]
    players: int = Field(..., ge=1, le=8)
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    date: datetime.date

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime.date) -> datetime.date:
        if v < datetime.date.today():
            raise ValueError("Booking date must be today or in the future.")
        return v


class FPVConfig(BaseModel):
    package: Literal["VEGAS", "MIAMI", "CALI"]
    players: int = Field(..., ge=1, le=6)
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    date: datetime.date

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, v: datetime.date) -> datetime.date:
        if v < datetime.date.today():
            raise ValueError("Booking date must be today or in the future.")
        return v


# ─── Main Booking Request ─────────────────────────────────────────────────────

class MissionConfig(BaseModel):
    """One game config entry. game_type + config dict."""
    game_type: Literal["VR_ARENA", "F1_MOTION", "FPV_GAMING"]
    config: dict  # raw config — validated per game type below


class CreateBookingRequest(BaseModel):
    branch: Literal["SURAT", "MUMBAI"] = Field(..., description="Which terminal to book")
    booking_date: Optional[datetime.date] = None
    pilot_name: str = Field(..., min_length=2, max_length=100)
    pilot_phone: str = Field(..., min_length=7, max_length=15)
    mission_configs: list[MissionConfig] = Field(..., min_length=1, description="At least one game required")

    @field_validator("pilot_phone")
    @classmethod
    def phone_must_be_numeric(cls, v: str) -> str:
        cleaned = v.replace("+", "").replace("-", "").replace(" ", "")
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits.")
        return v

    @field_validator("mission_configs")
    @classmethod
    def fpv_only_in_surat(cls, configs: list, info) -> list:
        """FPV Gaming is only available in the SURAT branch."""
        return configs


# ─── Status Update Request ────────────────────────────────────────────────────

class UpdateBookingStatusRequest(BaseModel):
    status: Literal["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED"]


# ─── Response Models ──────────────────────────────────────────────────────────

class BookingResponse(BaseModel):
    id: str
    branch: str
    status: str
    booking_date: Optional[str]
    created_at: str
    user_id: str
    pilot_name: Optional[str] = None
    pilot_phone: Optional[str] = None
    mission_configs: list[dict] = []
