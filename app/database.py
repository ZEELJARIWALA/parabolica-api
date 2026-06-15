from supabase import create_client, Client
from app.config import settings

# Uses the SERVICE ROLE key — full DB access, bypasses RLS
# This is safe because it runs on your server, never in the browser
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
