"""
routes/inquiries.py — Event inquiry API endpoints.

Endpoints:
  POST   /inquiries/               → Submit a new event inquiry (user)
  GET    /inquiries/?branch=SURAT  → List all inquiries (admin only)
  PATCH  /inquiries/{id}/status    → Update inquiry status (admin only)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from app.database import supabase
from app.models.inquiry import CreateInquiryRequest, UpdateInquiryStatusRequest
from app.dependencies.auth import get_current_user, get_admin_user, AuthenticatedUser

router = APIRouter(prefix="/inquiries", tags=["Inquiries"])


# ─── POST /inquiries/ ─────────────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_inquiry(
    payload: CreateInquiryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Submits a new event inquiry (Birthday, Kitty, Corporate, Walkthrough).
    Saves requester details and creates an inquiry record with status='NEW'.
    """
    inquiry_insert = {
        "user_id": user.user_id,
        "event_type": payload.event_type,
        "location": payload.location,
        "pilot_name": payload.pilot_name,
        "pilot_email": payload.pilot_email,
        "pilot_phone": payload.pilot_phone,
        "message": payload.message or "",
        "status": "NEW",
    }

    result = supabase.table("inquiries").insert(inquiry_insert).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit inquiry. Please try again.",
        )

    # ✅ Also upsert to profiles so admin sees this pilot's details
    supabase.table("profiles").upsert({
        "id": user.user_id,
        "full_name": payload.pilot_name,
        "phone_number": payload.pilot_phone,
    }).execute()

    return {
        "success": True,
        "inquiry_id": result.data[0]["id"],
        "message": "Your inquiry has been received. Our team will contact you within 24 hours.",
    }


# ─── GET /inquiries/ (admin) ──────────────────────────────────────────────────
@router.get("/")
def get_all_inquiries(
    branch: str = None,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """
    Admin-only: Returns all inquiries optionally filtered by location.
    Enforces terminal-based scoping for branch-specific admins.
    """
    # ✅ Terminal-scoped admin enforcement
    if admin.admin_terminal != "ALL":
        branch = admin.admin_terminal

    query = supabase.table("inquiries").select("*")

    if branch:
        query = query.eq("location", branch)

    inquiries_result = query.order("created_at", desc=True).execute()
    inquiries = inquiries_result.data or []

    # Merge profiles server-side
    if inquiries:
        user_ids = list(set(i["user_id"] for i in inquiries if i.get("user_id")))
        profiles_result = supabase.table("profiles") \
            .select("id, full_name, phone_number") \
            .in_("id", user_ids) \
            .execute()
        profiles_map = {p["id"]: p for p in (profiles_result.data or [])}

        for i in inquiries:
            i["profiles"] = profiles_map.get(i["user_id"])

    return {"inquiries": inquiries}


# ─── PATCH /inquiries/{id}/status (admin) ─────────────────────────────────────
@router.patch("/{inquiry_id}/status")
def update_inquiry_status(
    inquiry_id: str,
    payload: UpdateInquiryStatusRequest,
    admin: AuthenticatedUser = Depends(get_admin_user),
):
    """Admin-only: Updates an inquiry's status (NEW → QUOTED → CLOSED)."""
    inquiry = supabase.table("inquiries").select("location, status").eq("id", inquiry_id).maybe_single().execute()

    if not inquiry.data:
        raise HTTPException(status_code=404, detail="Inquiry not found.")

    # ✅ Security: Admin can only update inquiries in their terminal
    if admin.admin_terminal != "ALL" and inquiry.data["location"] != admin.admin_terminal:
        raise HTTPException(status_code=403, detail="Cannot modify inquiries outside your terminal.")

    # ✅ Business Rule: CLOSED inquiries can't be re-opened
    if inquiry.data["status"] == "CLOSED":
        raise HTTPException(status_code=400, detail="Closed inquiries cannot be re-opened.")

    supabase.table("inquiries").update({"status": payload.status}).eq("id", inquiry_id).execute()

    return {"success": True, "inquiry_id": inquiry_id, "new_status": payload.status}
