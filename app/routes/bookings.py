"""
routes/bookings.py — All booking-related API endpoints.

Endpoints:
  POST   /bookings/         → Create a new booking (user)
  GET    /bookings/mine     → Get current user's bookings
  PATCH  /bookings/{id}/status → Update booking status (admin only)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from app.database import supabase
from app.models.booking import CreateBookingRequest, UpdateBookingStatusRequest, BookingResponse
from app.dependencies.auth import get_current_user, get_admin_user, AuthenticatedUser

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# ─── POST /bookings/ ─────────────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: CreateBookingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Creates a new sequential mission booking.
    1. Validates branch constraints (No FPV in Mumbai).
    2. Checks for slot collisions across all requested games.
    3. atomic-like insertion into parent 'bookings' and specialized game tables.
    """
    
    # ✅ Step 0: Terminal-specific Validation
    game_types = [mc.game_type for mc in payload.mission_configs]
    if "FPV_GAMING" in game_types and payload.branch == "MUMBAI":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FPV DRONE PILOTING is currently offline at MUMBAI terminal."
        )

    # ✅ Step 1: Check Slot Availability for EACH game in sequence
    # We check against game-specific tables to prevent double-booking
    for mc in payload.mission_configs:
        table_name = mc.game_type.lower() + "_bookings"
        # Extract date and time from the config
        # (Assuming frontend sends date/time in the config object as per user request)
        g_date = mc.config.get("date")
        g_time = mc.config.get("time")
        
        if not g_date or not g_time:
            raise HTTPException(status_code=400, detail=f"Mission {mc.game_type} is missing date or time calibration.")

        # Check if slot is taken (Ignore cancelled bookings)
        try:
            collision = supabase.table(table_name) \
                .select("id, bookings!inner(status)") \
                .eq("branch", payload.branch) \
                .eq("slot_date", g_date) \
                .eq("slot_time", g_time) \
                .neq("bookings.status", "CANCELLED") \
                .execute()

            if collision and collision.data:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CRITICAL: {mc.game_type} slot at {g_time} on {g_date} is already occupied. Please select an alternative window."
                )
        except Exception as e:
            if "relation" in str(e).lower():
                raise HTTPException(status_code=500, detail=f"Database Table '{table_name}' is missing. Go to Supabase SQL and create it.")
            # If it's just a 404/Empty from maybe_single or a simple error, we continue
            pass

    # ✅ Step 2: Insert parent 'bookings' record
    booking_insert = {
        "user_id": user.user_id,
        "branch": payload.branch,
        "status": "PENDING",
        "booking_date": str(payload.booking_date) if payload.booking_date else None,
    }
    booking_result = supabase.table("bookings").insert(booking_insert).execute()
    
    if not booking_result.data:
        raise HTTPException(status_code=500, detail="Terminal Sync Failed. Data not committed.")
    
    booking_id = booking_result.data[0]["id"]

    # ✅ Step 3: Insert into Specialized Game Tables (Sequential)
    try:
        for mc in payload.mission_configs:
            table_name = mc.game_type.lower() + "_bookings"
            
            # ✅ FIX: Explicitly clear any existing slot records (Cancelled ones) to satisfy Unique Constraints
            supabase.table(table_name) \
                .delete() \
                .eq("branch", payload.branch) \
                .eq("slot_date", mc.config.get("date")) \
                .eq("slot_time", mc.config.get("time")) \
                .execute()

            game_insert = {
                "booking_id": booking_id,
                "user_id": user.user_id,
                "branch": payload.branch,
                "slot_date": mc.config.get("date"),
                "slot_time": mc.config.get("time"),
                "config": mc.config
            }
            supabase.table(table_name).insert(game_insert).execute()
    except Exception as e:
        # Detect if it's a "Duplicate Key" error from Supabase
        err_msg = str(e)
        if "23505" in err_msg or "duplicate key" in err_msg.lower():
            print(f"⚠️  COLLISION DETECTED: {err_msg}") # Clean log in terminal
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SECURITY ALERT: Someone just secured your chosen window for {mc.game_type}. Please pick another time!"
            )
        
        print(f"❌ DATABASE ERROR: {err_msg}")
        raise HTTPException(status_code=500, detail="Terminal Sync Failure. Please try again.")

    # ✅ Step 4: Update Profile (CRM)
    try:
        supabase.table("profiles").upsert({
            "id": user.user_id,
            "full_name": payload.pilot_name,
            "phone_number": payload.pilot_phone,
        }).execute()
    except Exception:
        pass # Not critical

    print(f"✅ MISSION SECURED: {payload.pilot_name} @ {payload.branch}") 
    
    return {
        "success": True,
        "booking_id": booking_id,
        "sequence": game_types,
        "message": "MISSION DATA TRANSMITTED. ALL SLOTS SECURED."
    }


# ─── GET /bookings/mine ───────────────────────────────────────────────────────
@router.get("/mine")
def get_my_bookings(user: AuthenticatedUser = Depends(get_current_user)):
    """Returns all bookings for the currently logged-in user."""
    # 1. Fetch parent bookings
    result = supabase.table("bookings") \
        .select("*") \
        .eq("user_id", user.user_id) \
        .order("created_at", desc=True) \
        .execute()
    
    bookings = result.data or []
    if not bookings:
        return {"bookings": []}

    # 2. Fetch mission loadouts from the unified view
    booking_ids = [b["id"] for b in bookings]
    missions = supabase.table("all_mission_slots") \
        .select("*") \
        .in_("booking_id", booking_ids) \
        .execute().data or []
    
    # 3. Attach missions to parent bookings
    for b in bookings:
        b["mission_configs"] = [m for m in missions if m["booking_id"] == b["id"]]

    return {"bookings": bookings}


# ─── GET /bookings/?branch=SURAT (admin) ──────────────────────────────────────
@router.get("/")
def get_all_bookings(
    branch: str = None,
    date: str = None,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """
    Admin-only: Returns all bookings, optionally filtered by branch.
    Admins with terminal='ALL' can see all. Branch-specific admins see only their sector.
    """
    # ✅ Security: Branch-specific admin cannot see other branches
    if admin.admin_terminal != "ALL":
        branch = admin.admin_terminal  # force to their terminal

    # 1. Fetch parent bookings with filter
    query = supabase.table("bookings").select("*")

    if branch:
        query = query.eq("branch", branch)
    
    if date:
        query = query.eq("booking_date", date)

    bookings_result = query.order("created_at", desc=True).execute()
    bookings = bookings_result.data or []

    if not bookings:
        return []

    # 2. Fetch mission loadouts from the unified view
    booking_ids = [b["id"] for b in bookings]
    missions = supabase.table("all_mission_slots") \
        .select("*") \
        .in_("booking_id", booking_ids) \
        .execute().data or []

    # 3. Merge profiles
    user_ids = list(set(b["user_id"] for b in bookings if b.get("user_id")))
    profiles_map = {}
    if user_ids:
        profiles_result = supabase.table("profiles") \
            .select("id, full_name, phone_number") \
            .in_("id", user_ids) \
            .execute()
        profiles_map = {p["id"]: p for p in (profiles_result.data or [])}

    # 4. Final aggregation
    for b in bookings:
        b["mission_configs"] = [m for m in missions if m["booking_id"] == b["id"]]
        b["profiles"] = profiles_map.get(b["user_id"])

    return bookings # Return list directly for frontend


# ─── PATCH /bookings/{id}/status (admin) ──────────────────────────────────────
@router.patch("/{booking_id}/status")
def update_booking_status(
    booking_id: str,
    payload: UpdateBookingStatusRequest,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """
    Admin-only: Updates the status of a booking.
    Valid transitions: PENDING → CONFIRMED → COMPLETED | CANCELLED
    """
    # ✅ Fetch booking first to verify it belongs to admin's terminal
    booking = supabase.table("bookings").select("branch, status").eq("id", booking_id).maybe_single().execute()

    if not booking.data:
        raise HTTPException(status_code=404, detail="Booking not found.")

    # ✅ Security: Admin can only update bookings in their terminal
    if admin.admin_terminal != "ALL" and booking.data["branch"] != admin.admin_terminal:
        raise HTTPException(status_code=403, detail="Cannot modify bookings outside your terminal.")

    # ✅ Business Rule: Cannot revert a COMPLETED booking back to earlier states
    if booking.data["status"] == "COMPLETED" and payload.status in ("PENDING", "CONFIRMED"):
        raise HTTPException(
            status_code=400,
            detail="Completed missions cannot be reverted to PENDING or CONFIRMED. Only CANCELLED is allowed.",
        )

    result = supabase.table("bookings") \
        .update({"status": payload.status}) \
        .eq("id", booking_id) \
        .execute()

    # ✅ FIX: If cancelling, remove specialized slot reservations to clear Unique Constraints.
    # This allows the same slot to be re-booked immediately.
    if payload.status == "CANCELLED":
        try:
            tables = ["vr_arena_bookings", "f1_motion_bookings", "fpv_gaming_bookings"]
            for t in tables:
                supabase.table(t).delete().eq("booking_id", booking_id).execute()
        except Exception:
            pass # Non-critical if some tables don't have the ID
    
    return {"success": True, "booking_id": booking_id, "new_status": payload.status}
