from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
import httpx
from app.database import supabase
from app.config import settings
import logging
import os

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Bot"])

# ─── Configuration (Green-API) ────────────────────────────────────────────────
ID_INSTANCE = os.getenv("GREEN_API_INSTANCE_ID")
API_TOKEN = os.getenv("GREEN_API_TOKEN")
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

Book your slot here: {booking_link}
"""

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        print(f"DEBUG: Received Webhook - {data}") # Render will always show 'print'
        
        type_webhook = data.get("typeWebhook")
        
        if type_webhook == "incomingMessageReceived":
            sender_data = data.get("senderData", {})
            chat_id = sender_data.get("chatId")
            name = sender_data.get("senderName", "Pilot")
            
            # Extract text carefully (Handles both standard and extended messages)
            message_data = data.get("messageData", {})
            body = ""
            
            if "textMessageData" in message_data:
                body = message_data["textMessageData"].get("textMessage", "")
            elif "extendedTextMessageData" in message_data:
                body = message_data["extendedTextMessageData"].get("text", "")
            
            print(f"DEBUG: Extracting text... Found: '{body}'")
            
            if body and chat_id:
                # Process in background
                background_tasks.add_task(process_green_api_interaction, chat_id, name, body)
            else:
                print("DEBUG: Ignored - Missing body or chat_id")
                
    except Exception as e:
        print(f"DEBUG ERROR in webhook: {e}")
        
    return {"status": "success"}

async def process_green_api_interaction(chat_id: str, name: str, text: str):
    print(f"DEBUG: Processing for {chat_id}...")
    try:
        # 1. Update/Create user in database
        clean_phone = chat_id.split("@")[0]
        
        print(f"DEBUG: Checking database for {clean_phone}...")
        user_query = supabase.table("whatsapp_contacts").select("*").eq("phone", clean_phone).execute()
        is_new_user = len(user_query.data) == 0
        
        if is_new_user:
            print(f"DEBUG: Inserting NEW pilot {clean_phone}")
            supabase.table("whatsapp_contacts").insert({
                "phone": clean_phone,
                "name": name,
                "last_message": text
            }).execute()
        else:
            print(f"DEBUG: Updating existing pilot {clean_phone}")
            supabase.table("whatsapp_contacts").update({
                "last_message": text,
                "name": name 
            }).eq("phone", clean_phone).execute()

        # 2. Logic for Auto-Reply
        response_text = ""
        booking_link = f"{settings.FRONTEND_URL}/booking"
        contact_phone = "+91 63542 28913"
        text_lower = text.lower().strip()
        
        # Exact trigger for the button
        trigger_msg = "hello parabolica! i'm interested in booking a session."
        
        print(f"DEBUG: Checking trigger for text: '{text_lower}'")

        if trigger_msg in text_lower or any(k in text_lower for k in ["price", "pricing", "rate", "cost"]):
            print(f"DEBUG: Trigger MATCHED. Preparing pricing catalog.")
            response_text = (
                f"Hello {name}! 🛰️ We're thrilled to have you at Parabolica.\n\n"
                f"Here is our current mission catalog and exclusive offers:\n"
                f"{PRICING_CATALOG.format(booking_link=booking_link)}\n\n"
                f"📞 *Need to talk to us?* Call our Command Center at {contact_phone}\n\n"
                f"See you in the Arena! 🏎️💨"
            )
        elif is_new_user or any(k in text_lower for k in ["hello", "hi", "hey"]):
            print(f"DEBUG: Trigger: Greeting. Sending menu.")
            response_text = f"Welcome to Parabolica, {name}! 🛰️\n\nAre you looking for *PRICING* or do you want to *BOOK* a session?\n\nType 'Pricing' for our latest packages!"

        # 3. Send via Green-API
        if response_text:
            print(f"DEBUG: Sending message to Green-API for {chat_id}")
            await send_green_api_message(chat_id, response_text)
        else:
            print(f"DEBUG: No auto-reply response generated.")
            
    except Exception as e:
        print(f"DEBUG DATABASE ERROR: {e}")

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
