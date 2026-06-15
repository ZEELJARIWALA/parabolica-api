"""
routes/slots.py — Availability and slot checking endpoints.
Used by the frontend to disable buttons for already-booked windows.
"""

from fastapi import APIRouter, HTTPException, Query
from app.database import supabase
from typing import List, Literal

router = APIRouter(prefix="/slots", tags=["Slots"])

@router.get("/availability")
def get_booked_slots(
    branch: Literal["SURAT", "MUMBAI"],
    game_type: Literal["VR_ARENA", "F1_MOTION", "FPV_GAMING"],
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date YYYY-MM-DD")
):
    """
    Returns a list of booked time slots for a specific game and date.
    Frontend uses this to render 'Unavailable' UI states.
    """
    table_name = game_type.lower() + "_bookings"
    
    # ✅ FIX: Only count slots from bookings that are NOT cancelled
    result = supabase.table(table_name) \
        .select("slot_time, bookings!inner(status)") \
        .eq("branch", branch) \
        .eq("slot_date", date) \
        .neq("bookings.status", "CANCELLED") \
        .execute()
    
    booked_times = [item["slot_time"] for item in (result.data or [])]
    
    return {
        "branch": branch,
        "date": date,
        "game_type": game_type,
        "booked_slots": booked_times
    }

@router.get("/all-available")
def get_all_booked_slots(
    branch: Literal["SURAT", "MUMBAI"],
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
):
    """
    Returns booked slots for ALL games in one call. 
    Ideal for the initialization of the booking calendar.
    """
    games = ["VR_ARENA", "F1_MOTION", "FPV_GAMING"]
    all_booked = {}
    
    for game in games:
        table_name = game.lower() + "_bookings"
        res = supabase.table(table_name) \
            .select("slot_time, bookings!inner(status)") \
            .eq("branch", branch) \
            .eq("slot_date", date) \
            .neq("bookings.status", "CANCELLED") \
            .execute()
        all_booked[game] = [item["slot_time"] for item in (res.data or [])]
        
    return {
        "branch": branch,
        "date": date,
        "booked": all_booked
    }
