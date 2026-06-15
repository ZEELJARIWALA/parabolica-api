"""
routes/admin.py — Admin-only dashboard data endpoints.

Endpoints:
  GET /admin/stats?branch=SURAT → Aggregate stats for the Intel Overview tab
  GET /admin/pilots?branch=SURAT → Pilot registry (unique users aggregated)
  GET /admin/verify              → Verify if current user is admin + get their terminal
"""

from fastapi import APIRouter, Depends, HTTPException
from app.database import supabase
from app.dependencies.auth import get_current_user, get_admin_user, AuthenticatedUser
from collections import defaultdict

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── GET /admin/verify ────────────────────────────────────────────────────────
@router.get("/verify")
def verify_admin(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Checks if the current user is an admin.
    Frontend calls this on page load to decide whether to show dashboard or deny access.
    """
    result = supabase.table("admins") \
        .select("terminal, name, email") \
        .eq("id", user.user_id) \
        .maybe_single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=403, detail="Not an admin.")

    return {
        "is_admin": True,
        "terminal": result.data["terminal"],
        "name": result.data["name"],
        "email": result.data["email"],
    }


# ─── GET /admin/stats ─────────────────────────────────────────────────────────
@router.get("/stats")
def get_stats(
    branch: str = None,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """
    Admin-only: Returns aggregated stats for the Intel Overview tab.
    Includes mission counts, game popularity, and inquiry pipeline.
    """
    if admin.admin_terminal != "ALL":
        branch = admin.admin_terminal

    # Fetch bookings
    bq = supabase.table("bookings").select("id, status, created_at, mission_configs(game_type)")
    if branch:
        bq = bq.eq("branch", branch)
    bookings = bq.execute().data or []

    # Fetch inquiries
    iq = supabase.table("inquiries").select("id, status, created_at")
    if branch:
        iq = iq.eq("location", branch)
    inquiries = iq.execute().data or []

    # ✅ Aggregate stats
    from datetime import date
    today_str = date.today().isoformat()

    total_bookings = len(bookings)
    today_bookings = sum(1 for b in bookings if b["created_at"].startswith(today_str))
    confirmed = sum(1 for b in bookings if b["status"] == "CONFIRMED")
    completed = sum(1 for b in bookings if b["status"] == "COMPLETED")
    conversion_rate = round((confirmed / total_bookings * 100), 1) if total_bookings else 0

    # Game popularity
    game_counts = defaultdict(int)
    for b in bookings:
        for mc in b.get("mission_configs", []):
            game_counts[mc["game_type"]] += 1

    total_inquiries = len(inquiries)
    active_inquiries = sum(1 for i in inquiries if i["status"] != "CLOSED")
    new_leads = sum(1 for i in inquiries if i["status"] == "NEW")

    return {
        "bookings": {
            "total": total_bookings,
            "today": today_bookings,
            "confirmed": confirmed,
            "completed": completed,
            "conversion_rate_percent": conversion_rate,
        },
        "game_popularity": dict(game_counts),
        "inquiries": {
            "total": total_inquiries,
            "active": active_inquiries,
            "new_leads": new_leads,
        },
    }


# ─── GET /admin/pilots ────────────────────────────────────────────────────────
@router.get("/pilots")
def get_pilot_registry(
    branch: str = None,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """
    Admin-only: Returns the Pilot Registry — all unique users, their booking count,
    inquiry count, and last activity date. Used for the PILOTS tab in the dashboard.
    """
    if admin.admin_terminal != "ALL":
        branch = admin.admin_terminal

    # Fetch all bookings for this terminal
    bq = supabase.table("bookings").select("user_id, created_at")
    if branch:
        bq = bq.eq("branch", branch)
    bookings = bq.execute().data or []

    # Fetch all inquiries for this terminal
    iq = supabase.table("inquiries").select("user_id, created_at")
    if branch:
        iq = iq.eq("location", branch)
    inquiries = iq.execute().data or []

    # Aggregate by user_id
    pilot_map = defaultdict(lambda: {"bookings": 0, "inquiries": 0, "last_seen": None})

    for b in bookings:
        uid = b["user_id"]
        pilot_map[uid]["bookings"] += 1
        if not pilot_map[uid]["last_seen"] or b["created_at"] > pilot_map[uid]["last_seen"]:
            pilot_map[uid]["last_seen"] = b["created_at"]

    for i in inquiries:
        uid = i["user_id"]
        pilot_map[uid]["inquiries"] += 1
        if not pilot_map[uid]["last_seen"] or i["created_at"] > pilot_map[uid]["last_seen"]:
            pilot_map[uid]["last_seen"] = i["created_at"]

    # Fetch profiles for all unique user IDs
    all_user_ids = list(pilot_map.keys())
    if not all_user_ids:
        return {"pilots": []}

    profiles = supabase.table("profiles") \
        .select("id, full_name, phone_number") \
        .in_("id", all_user_ids) \
        .execute().data or []

    profiles_map = {p["id"]: p for p in profiles}

    pilots = []
    for uid, data in pilot_map.items():
        profile = profiles_map.get(uid, {})
        pilots.append({
            "user_id": uid,
            "full_name": profile.get("full_name", "ANONYMOUS"),
            "phone_number": profile.get("phone_number", "—"),
            "bookings": data["bookings"],
            "inquiries": data["inquiries"],
            "last_seen": data["last_seen"],
        })

    # Sort by most recent activity
    pilots.sort(key=lambda p: p["last_seen"] or "", reverse=True)

    return {"pilots": pilots}
