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

def extract_text_from_webhook(message_data: dict) -> str:
    if not message_data:
        return ""
    
    type_message = message_data.get("typeMessage")
    
    # 1. Standard text message
    if type_message == "textMessage" and "textMessageData" in message_data:
        return message_data["textMessageData"].get("textMessage", "")
        
    # 2. Extended text message (links, quotes, etc.)
    if type_message == "extendedTextMessage" and "extendedTextMessageData" in message_data:
        return message_data["extendedTextMessageData"].get("text", "")
        
    # 3. Interactive Button Reply
    if type_message == "interactiveButtonReply" and "interactiveButtonReply" in message_data:
        return message_data["interactiveButtonReply"].get("buttonText", "")
        
    # 4. Template Button Reply
    if type_message == "templateButtonsReply" and "templateButtonsReply" in message_data:
        return message_data["templateButtonsReply"].get("selectedDisplayText", "")
        
    # 5. List message reply
    if type_message == "listMessage" and "listMessageData" in message_data:
        return message_data["listMessageData"].get("title", "")
        
    # 6. File / Media / Document caption
    if "fileMessageData" in message_data:
        return message_data["fileMessageData"].get("caption", "")
        
    # Fallback to search recursively for text fields
    for key in ["textMessageData", "extendedTextMessageData", "interactiveButtonReply", "templateButtonsReply", "listMessageData", "fileMessageData"]:
        if key in message_data and isinstance(message_data[key], dict):
            for subkey in ["textMessage", "text", "buttonText", "selectedDisplayText", "title", "caption"]:
                val = message_data[key].get(subkey)
                if val:
                    return str(val)
                    
    return ""

@router.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print(f"DEBUG STEP 1: Received Webhook Data -> {data}")
        
        type_webhook = data.get("typeWebhook")
        print(f"DEBUG Webhook Type: {type_webhook}")
        
        if type_webhook == "incomingMessageReceived":
            sender_data = data.get("senderData") or {}
            chat_id = sender_data.get("chatId")
            
            # Robust extraction of name to bypass Any None/null DB issues
            raw_sender_name = sender_data.get("senderName")
            raw_chat_name = sender_data.get("chatName")
            raw_contact_name = sender_data.get("senderContactName")
            
            name = raw_sender_name or raw_chat_name or raw_contact_name or "Pilot"
            name = name.strip()
            if not name:
                name = "Pilot"
            
            message_data = data.get("messageData") or {}
            text = extract_text_from_webhook(message_data)
            
            print(f"DEBUG STEP 2: Text extracted -> '{text}', chat_id -> '{chat_id}', name -> '{name}'")
            
            if text and chat_id:
                # RUN IMMEDIATELY
                await process_green_api_interaction(chat_id, name, text)
            else:
                print(f"DEBUG: Missing text or chat_id (text={text}, chat_id={chat_id})")
        else:
            print(f"DEBUG: Ignored Webhook Type: {type_webhook}")
                
    except Exception as e:
        print(f"!!! CRITICAL WEBHOOK ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    return {"status": "success"}

async def process_green_api_interaction(chat_id: str, name: str, text: str):
    print(f"DEBUG STEP 3: Starting Database/Reply logic for {chat_id}")
    try:
        # 1. Update/Create user in database
        clean_phone = chat_id.split("@")[0]
        
        user_query = supabase.table("whatsapp_contacts").select("*").eq("phone", clean_phone).execute()
        is_new_user = len(user_query.data) == 0
        
        if is_new_user:
            print(f"DEBUG: Inserting brand new user: {clean_phone} / {name}")
            supabase.table("whatsapp_contacts").insert({
                "phone": clean_phone, 
                "name": name, 
                "last_message": text, 
                "is_returning": False
            }).execute()
        else:
            print(f"DEBUG: Updating existing user: {clean_phone} / {name}")
            supabase.table("whatsapp_contacts").update({
                "last_message": text, 
                "name": name, 
                "is_returning": True
            }).eq("phone", clean_phone).execute()

        # 2. Logic for Universal Response
        response_text = ""
        booking_link = "https://parabolica.co.in/booking"
        info_link = "https://parabolica.co.in"
        contact_phone = "+91 73837 56561"
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
        import traceback
        traceback.print_exc()

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
