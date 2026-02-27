"""
Supabase connection management.
Uses service_role key for full DB access (server-side only).
"""

import ssl
import httpx
import streamlit as st
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
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


def _make_httpx_client() -> httpx.Client:
    """Create an httpx Client with SSL verification disabled.

    This is needed in corporate/proxy networks where a custom CA
    intercepts TLS traffic, causing CERTIFICATE_VERIFY_FAILED errors.
    """
    return httpx.Client(verify=False, timeout=httpx.Timeout(120.0))


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

    # Pass a custom httpx client that skips SSL cert verification
    options = SyncClientOptions(httpx_client=_make_httpx_client())
    _client = create_client(url, key, options=options)
    return _client


def health_check() -> bool:
    """Quick DB connectivity test."""
    try:
        client = get_supabase()
        client.table("users").select("id").limit(1).execute()
        return True
    except Exception:
        return False
