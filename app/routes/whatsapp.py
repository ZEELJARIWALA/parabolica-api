from fastapi import APIRouter, Request
import httpx
from app.database import supabase
from app.config import settings
import os

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Bot"])

# ─── Gateway URL (Node.js Self-Hosted WhatsApp Gateway) ───────────────────────
GATEWAY_URL = settings.WHATSAPP_GATEWAY_URL

# ─── Contact Numbers ──────────────────────────────────────────────────────────
SURAT_PHONE = "+91 87589 02732"
MUMBAI_PHONE = "+91 99872 07826"

# ─── Pricing Data (Surat Terminal — Opening Special 25% OFF) ──────────────────
PRICING_CATALOG = """🚀 *PARABOLICA — OPENING SPECIAL (25% OFF)* 🚀
⚡ *Surat Terminal Only — Limited Time Offer!*

🥽 *VR GAMING*
• 15 Minutes: ₹299
• 30 Minutes: ₹499
• 45 Minutes: ₹699

🏎️ *F1 STATIC SIM RACING*
• 06 Laps: ₹299
• 10 Laps: ₹499
• 15 Laps: ₹699
• 20 Laps: ₹899

🔥 *COMBO PACKAGES (BEST VALUE)*
• *Combo 1 – Starter:* VR (15 Min) + F1 Static (6 Laps) → ₹549
• *Combo 2 – Explorer:* VR (30 Min) + F1 Static (10 Laps) → ₹899
• *Combo 3 – Pro:* VR (45 Min) + F1 Static (15 Laps) → ₹1,249

📞 *Enquiries:*
• *Surat Terminal:* {surat}
• *Mumbai Terminal:* {mumbai}

🌐 Book Now: https://parabolica.co.in/booking""".format(surat=SURAT_PHONE, mumbai=MUMBAI_PHONE)

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
        text_lower = text.lower().strip()

        trigger_msg = "hello parabolica! i'm interested in booking a session."

        if trigger_msg in text_lower or any(k in text_lower for k in ["price", "pricing", "rate", "cost", "offer"]):
            response_text = (
                f"Hello {name}! 🛰️ Thanks for reaching out.\n\n"
                f"Here are our current offers:\n"
                f"{PRICING_CATALOG}\n\n"
                f"⚠️ *Note:* These prices are for *Surat Terminal only* — Limited Time Opening Offer!\n\n"
                f"See you in the Arena! 🏎️💨"
            )
        elif "surat" in text_lower:
            response_text = (
                f"🏎️ *Parabolica Surat Terminal*\n\n"
                f"📍 *Location Map:*\n"
                f"🔗 https://maps.app.goo.gl/pmxQ27pFZYqMBCATA\n\n"
                f"📞 *For Enquiries:* {SURAT_PHONE}\n\n"
                f"Looking forward to seeing you at the Grid! 🏁"
            )
        elif "mumbai" in text_lower:
            response_text = (
                f"🏎️ *Parabolica Mumbai Terminal*\n\n"
                f"📍 *Location Map:*\n"
                f"🔗 https://maps.app.goo.gl/4uFgUNyXNAmSNz1g6\n\n"
                f"📞 *For Enquiries:* {MUMBAI_PHONE}\n\n"
                f"Looking forward to seeing you at the Grid! 🏁"
            )
        else:
            response_text = (
                f"Hello {name}! 🛰️ We've received your message.\n\n"
                f"To help you immediately, please visit our portal to view *LIVE PRICING* and *BOOK* your session:\n"
                f"🔗 {info_link}\n\n"
                f"👉 Or reply *\"offer\"* to see our special pricing and packages!\n\n"
                f"📍 *Our Locations:*\n"
                f"• *Surat Terminal:* https://maps.app.goo.gl/pmxQ27pFZYqMBCATA\n"
                f"• *Mumbai Terminal:* https://maps.app.goo.gl/4uFgUNyXNAmSNz1g6\n\n"
                f"📞 *Enquiries:*\n"
                f"• *Surat:* {SURAT_PHONE}\n"
                f"• *Mumbai:* {MUMBAI_PHONE}"
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
