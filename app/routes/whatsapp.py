from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
import httpx
from app.database import supabase
from app.config import settings
import logging
import os

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Bot"])

# ─── Configuration (Green-API) ────────────────────────────────────────────────
ID_INSTANCE = settings.GREEN_API_INSTANCE_ID
API_TOKEN = settings.GREEN_API_TOKEN
BASE_URL = f"https://api.green-api.com/waInstance{ID_INSTANCE}"

# ─── Pricing Data ─────────────────────────────────────────────────────────────
PRICING_CATALOG = """
* PARABOLICA MISSION PRICING*

*1. F1 RACING SIMULATION (Motion)*
• Solo Session: ₹1,500
• Pro League: ₹2,500
• Sprint Mode: ₹1,000

*2. VR ARENA (Immersive)*
• 30 Min Mission: ₹1,200
• 60 Min Mission: ₹2,000

*3. FPV DRONE TRAINING*
• Basic Package: ₹1,000
• Advanced Pilot: ₹2,500

* CURRENT OFFERS:*
• Book 3+ pilots and get 15% OFF!
• First Mission Discount: Use code 'PILOTID01' for ₹200 off!

Book your slot here: https://parabolica.co.in/booking
"""

@router.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print(f"DEBUG STEP 1: Received Webhook Data")
        
        type_webhook = data.get("typeWebhook")
        if type_webhook == "incomingMessageReceived":
            sender_data = data.get("senderData", {})
            chat_id = sender_data.get("chatId")
            name = sender_data.get("senderName", "Pilot")
            
            message_data = data.get("messageData", {})
            text = ""
            if "textMessageData" in message_data:
                text = message_data["textMessageData"].get("textMessage", "")
            elif "extendedTextMessageData" in message_data:
                text = message_data["extendedTextMessageData"].get("text", "")
            
            print(f"DEBUG STEP 2: Text extracted -> '{text}'")
            
            if text and chat_id:
                # RUN IMMEDIATELY
                await process_green_api_interaction(chat_id, name, text)
            else:
                print("DEBUG: Missing text or chat_id")
                
    except Exception as e:
        print(f"!!! CRITICAL WEBHOOK ERROR: {e}")
        
    return {"status": "success"}

async def process_green_api_interaction(chat_id: str, name: str, text: str):
    print(f"DEBUG STEP 3: Starting Database/Reply logic for {chat_id}")
    try:
        # 1. Update/Create user in database
        clean_phone = chat_id.split("@")[0]
        
        user_query = supabase.table("whatsapp_contacts").select("*").eq("phone", clean_phone).execute()
        is_new_user = len(user_query.data) == 0
        
        if is_new_user:
            supabase.table("whatsapp_contacts").insert({
                "phone": clean_phone, "name": name, "last_message": text, "is_returning": False
            }).execute()
        else:
            supabase.table("whatsapp_contacts").update({
                "last_message": text, "name": name, "is_returning": True
            }).eq("phone", clean_phone).execute()

        # 2. Logic for Universal Response
        response_text = ""
        booking_link = "https://parabolica.co.in/booking"
        info_link = "https://parabolica.co.in"
        contact_phone = "+91 63542 28913"
        text_lower = text.lower().strip()
        
        trigger_msg = "hello parabolica! i'm interested in booking a session."

        if trigger_msg in text_lower or any(k in text_lower for k in ["price", "pricing", "rate", "cost", "offer"]):
            # FULL PRICING INFO
            response_text = (
                f"Hello {name}! 🛰️ Thanks for reaching out.\n\n"
                f"Here is our current mission catalog and exclusive offers:\n"
                f"{PRICING_CATALOG}\n\n"
                f"📞 *Need to talk to us?* Call our Command Center at {contact_phone}\n\n"
                f"See you in the Arena! 🏎️💨"
            )
        else:
            # UNIVERSAL FALLBACK
            response_text = (
                f"Hello {name}! 🛰️ We've received your message.\n\n"
                f"To help you immediately, please visit the link below to view our *LIVE PRICING*, *OFFERS*, and *BOOK* your session:\n\n"
                f"🔗 {info_link}\n\n"
                f"If you'd rather speak to us directly, call: {contact_phone}"
            )

        # 3. Send via Green-API
        if response_text:
            await send_green_api_message(chat_id, response_text)
            
    except Exception as e:
        print(f"DEBUG DATABASE/LOGIC ERROR: {e}")

async def send_green_api_message(chat_id: str, message: str):
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    payload = {"chatId": chat_id, "message": message}
    
    print(f"DEBUG: Requesting Green-API: {url}")
    async with httpx.AsyncClient() as client:
        try:
            if ID_INSTANCE and API_TOKEN:
                resp = await client.post(url, json=payload)
                print(f"DEBUG: Green-API Result -> {resp.status_code}: {resp.text}")
                resp.raise_for_status()
            else:
                print("DEBUG: ERROR - GREEN_API_INSTANCE_ID or TOKEN missing in environment.")
        except Exception as e:
            print(f"DEBUG SEND ERROR: {e}")
