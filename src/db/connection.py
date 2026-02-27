"""
Supabase connection management.
Uses service_role key for full DB access (server-side only).
"""

import streamlit as st
from supabase import create_client, Client
from typing import Optional

_client: Optional[Client] = None


def _get_secret(key: str, default: str = "") -> str:
    """Read secret from Streamlit secrets or env."""
    try:
        val = st.secrets.get(key, None)
        if val:
            return str(val)
    except Exception:
        pass
    import os
    return os.environ.get(key, default)


def get_supabase() -> Client:
    """Get or create a Supabase client (singleton)."""
    global _client
    if _client is not None:
        return _client

    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .streamlit/secrets.toml "
            "or environment variables."
        )

    _client = create_client(url, key)
    return _client


def health_check() -> bool:
    """Quick DB connectivity test."""
    try:
        client = get_supabase()
        client.table("users").select("id").limit(1).execute()
        return True
    except Exception:
        return False
