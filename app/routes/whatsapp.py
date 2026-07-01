from fastapi import APIRouter, Request
import httpx
from app.database import supabase
from app.config import settings
import os

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Bot"])

# ─── Gateway URL (Node.js Self-Hosted WhatsApp Gateway) ───────────────────────
GATEWAY_URL = settings.WHATSAPP_GATEWAY_URL

# ─── Pricing Data ─────────────────────────────────────────────────────────────
PRICING_CATALOG = """🚀 *PARABOLICA - LAUNCH OFFER (25% OFF)* 🚀

🏎️ *F1 MOTION RACING*
• 6 Laps: ₹599
• 15 Min (10 Laps): ₹699
• 30 Min (15 Laps): ₹899
• 45 Min (20 Laps): ₹1,099

🚥 *F1 STATIC RACING*
• 6 Laps: ₹399
• 15 Min (10 Laps): ₹599
• 30 Min (15 Laps): ₹799
• 45 Min (20 Laps): ₹999

🥽 *VR GAMING*
• 15 Min: ₹799
• 30 Min: ₹999
• 45 Min: ₹1,149

🔥 *SPECIAL OFFERS*
• Group Discount Available!
• Call us for custom booking: 7383756561

🌐 Book Now: https://parabolica.co.in/booking"""

# ─── Webhook: Receives forwarded messages from Node.js Gateway ─────────────────
@router.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print(f"DEBUG STEP 1: Received from Gateway -> {data}")

        phone = data.get("phone")
        name = (data.get("name") or "Pilot").strip() or "Pilot"
        text = (data.get("text") or "").strip()

        print(f"DEBUG STEP 2: Phone='{phone}', Name='{name}', Text='{text}'")

        if phone and text:
            await process_whatsapp_message(phone, name, text)
        else:
            print(f"DEBUG: Skipping — missing phone or text")

    except Exception as e:
        print(f"!!! CRITICAL WEBHOOK ERROR: {e}")
        import traceback
        traceback.print_exc()

    return {"status": "success"}

# ─── Core Logic: Database + Auto-Reply ─────────────────────────────────────────
async def process_whatsapp_message(phone: str, name: str, text: str):
    print(f"DEBUG STEP 3: Processing message from {phone}")
    try:
        # 1. Upsert contact in database
        user_query = supabase.table("whatsapp_contacts").select("*").eq("phone", phone).execute()
        is_new_user = len(user_query.data) == 0

        if is_new_user:
            print(f"DEBUG: Inserting NEW contact: {phone} / {name}")
            supabase.table("whatsapp_contacts").insert({
                "phone": phone,
                "name": name,
                "last_message": text,
                "is_returning": False
            }).execute()
        else:
            print(f"DEBUG: Updating EXISTING contact: {phone} / {name}")
            supabase.table("whatsapp_contacts").update({
                "last_message": text,
                "name": name,
                "is_returning": True
            }).eq("phone", phone).execute()

        # 2. Build response
        response_text = ""
        info_link = "https://parabolica.co.in"
        contact_phone = "+91 73837 56561"
        text_lower = text.lower().strip()

        trigger_msg = "hello parabolica! i'm interested in booking a session."

        if trigger_msg in text_lower or any(k in text_lower for k in ["price", "pricing", "rate", "cost", "offer"]):
            response_text = (
                f"Hello {name}! 🛰️ Thanks for reaching out.\n\n"
                f"Here is our current mission catalog and exclusive offers:\n"
                f"{PRICING_CATALOG}\n\n"
                f"📞 *Need to talk to us?* Call our Command Center at {contact_phone}\n\n"
                f"See you in the Arena! 🏎️💨"
            )
        elif "surat" in text_lower:
            response_text = (
                f"🏎️ *Parabolica Surat Terminal Location Map:*\n"
                f"🔗 https://maps.app.goo.gl/pmxQ27pFZYqMBCATA\n\n"
                f"Looking forward to seeing you at the Grid! 🏁"
            )
        elif "mumbai" in text_lower:
            response_text = (
                f"🏎️ *Parabolica Mumbai Terminal Location Map:*\n"
                f"🔗 https://maps.app.goo.gl/4uFgUNyXNAmSNz1g6\n\n"
                f"Looking forward to seeing you at the Grid! 🏁"
            )
        else:
            response_text = (
                f"Hello {name}! 🛰️ We've received your message.\n\n"
                f"To help you immediately, please visit our portal to view *LIVE PRICING* and *BOOK* your session:\n"
                f"🔗 {info_link}\n\n"
                f"👉 Or reply **\"offer\"** to see our special pricing and packages!\n\n"
                f"📍 *Our Locations:*\n"
                f"• *Surat Terminal:* https://maps.app.goo.gl/pmxQ27pFZYqMBCATA\n"
                f"• *Mumbai Terminal:* https://maps.app.goo.gl/4uFgUNyXNAmSNz1g6\n\n"
                f"📞 *Direct Support:* Call our center at {contact_phone}"
            )

        # 3. Send reply via Gateway
        if response_text:
            await send_via_gateway(phone, response_text)

    except Exception as e:
        print(f"DEBUG DATABASE/LOGIC ERROR: {e}")
        import traceback
        traceback.print_exc()

# ─── Send message via Node.js Gateway ──────────────────────────────────────────
async def send_via_gateway(to_phone: str, message: str):
    url = f"{GATEWAY_URL}/send"
    payload = {"to": to_phone, "message": message}

    print(f"DEBUG: Sending via Gateway -> {url} / To: {to_phone}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"DEBUG: Gateway Response -> {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        except Exception as e:
            print(f"DEBUG GATEWAY SEND ERROR: {e}")
