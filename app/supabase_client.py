from supabase import create_client, Client
from app.config import settings

# Create Supabase client with service key for backend operations
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY  # Use service key for backend operations
)