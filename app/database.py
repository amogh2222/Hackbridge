"""
HackBridge — Database Configuration
Singleton Supabase client initialized from environment variables.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Returns a cached Supabase client instance.
    Uses @lru_cache so the client is created once and reused across
    all request handlers — avoids redundant HTTP connection setup.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in your .env file. "
            "Copy .env.example → .env and fill in your Supabase project credentials."
        )

    return create_client(url, key)
