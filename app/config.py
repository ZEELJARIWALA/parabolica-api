from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Add these to allow the WhatsApp keys
    GREEN_API_INSTANCE_ID: str = ""
    GREEN_API_TOKEN: str = ""
    
    # Meta WhatsApp Business Cloud API Settings
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"  # This prevents the crash if other variables exist

settings = Settings()
