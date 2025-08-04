from supabase import create_client, Client
from app.config import settings

# Create Supabase client with service key for backend operations
# Service key bypasses RLS and foreign key constraints, perfect for testing
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY,  # Use service key for backend operations
    options={
        "db": {
            "schema": "public"
        },
        "auth": {
            "auto_refresh_token": False,
            "persist_session": False
        }
    }
)