"""
Data CRUD — saved analyses, reports, portfolios, watchlists, user API keys.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
from src.db.connection import get_supabase


# ═══════════════════════════════════════════════════════════
# ENCRYPTION HELPERS (for user API keys)
# ═══════════════════════════════════════════════════════════

def _get_fernet() -> Fernet:
    """Get Fernet cipher from the ENCRYPTION_KEY secret."""
    try:
        import streamlit as st
        key = st.secrets.get("ENCRYPTION_KEY", "")
    except Exception:
        key = ""
    if not key:
        import os
        key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key for storage."""
    f = _get_fernet()
    return f.encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key."""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode("utf-8")).decode("utf-8")


# ═══════════════════════════════════════════════════════════
# SAVED ANALYSES
# ═══════════════════════════════════════════════════════════

def save_analysis(
    user_id: str,
    ticker: str,
    company_name: str,
    results_json: dict,
) -> Optional[Dict]:
    """Save an analysis result for a user."""
    db = get_supabase()
    # Serialize: strip non-serializable objects
    safe_json = _safe_serialize(results_json)
    result = db.table("saved_analyses").insert({
        "user_id": user_id,
        "ticker": ticker.upper(),
        "company_name": company_name,
        "results_json": safe_json,
    }).execute()
    return result.data[0] if result.data else None


def get_saved_analyses(user_id: str, limit: int = 30) -> List[Dict]:
    """List saved analyses for a user."""
    db = get_supabase()
    result = db.table("saved_analyses").select(
        "id, ticker, company_name, created_at"
    ).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data or []


def get_saved_analysis(analysis_id: str, user_id: str) -> Optional[Dict]:
    """Get a specific saved analysis."""
    db = get_supabase()
    result = db.table("saved_analyses").select("*").eq(
        "id", analysis_id
    ).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def delete_saved_analysis(analysis_id: str, user_id: str) -> bool:
    """Delete a saved analysis."""
    db = get_supabase()
    result = db.table("saved_analyses").delete().eq(
        "id", analysis_id
    ).eq("user_id", user_id).execute()
    return bool(result.data)


def count_saved_analyses(user_id: str) -> int:
    """Count total saved analyses for a user."""
    db = get_supabase()
    result = db.table("saved_analyses").select(
        "id", count="exact"
    ).eq("user_id", user_id).execute()
    return result.count or 0


# ═══════════════════════════════════════════════════════════
# SAVED REPORTS
# ═══════════════════════════════════════════════════════════

def save_report(
    user_id: str,
    ticker: str,
    company_name: str,
    report_markdown: str,
    llm_provider: str = "",
    llm_model: str = "",
) -> Optional[Dict]:
    """Save an AI-generated report."""
    db = get_supabase()
    result = db.table("saved_reports").insert({
        "user_id": user_id,
        "ticker": ticker.upper(),
        "company_name": company_name,
        "report_markdown": report_markdown,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    }).execute()
    return result.data[0] if result.data else None


def get_saved_reports(user_id: str, limit: int = 30) -> List[Dict]:
    """List saved reports for a user."""
    db = get_supabase()
    result = db.table("saved_reports").select(
        "id, ticker, company_name, llm_provider, llm_model, created_at"
    ).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data or []


def get_saved_report(report_id: str, user_id: str) -> Optional[Dict]:
    """Get a specific saved report."""
    db = get_supabase()
    result = db.table("saved_reports").select("*").eq(
        "id", report_id
    ).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def delete_saved_report(report_id: str, user_id: str) -> bool:
    """Delete a saved report."""
    db = get_supabase()
    result = db.table("saved_reports").delete().eq(
        "id", report_id
    ).eq("user_id", user_id).execute()
    return bool(result.data)


def count_daily_reports(user_id: str) -> int:
    """Count AI reports generated today (for rate limiting)."""
    db = get_supabase()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    result = db.table("saved_reports").select(
        "id", count="exact"
    ).eq("user_id", user_id).gte("created_at", today_start).execute()
    return result.count or 0


# ═══════════════════════════════════════════════════════════
# DAILY USAGE TRACKING (rate_limits table)
# ═══════════════════════════════════════════════════════════

def count_daily_usage(user_id: str, action_type: str) -> int:
    """
    Count how many times a user has performed an action today.
    Uses the rate_limits table with window_start >= today 00:00 UTC.
    """
    db = get_supabase()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    result = db.table("rate_limits").select(
        "request_count"
    ).eq("user_id", user_id).eq(
        "action_type", action_type
    ).gte("window_start", today_start).execute()

    if result.data:
        return sum(row.get("request_count", 0) for row in result.data)
    return 0


def record_daily_usage(user_id: str, action_type: str):
    """
    Record one usage of an action for today.
    Upserts into rate_limits: increments request_count if today's row exists,
    otherwise inserts a new row.
    """
    db = get_supabase()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    # Check if today's row exists
    existing = db.table("rate_limits").select("id, request_count").eq(
        "user_id", user_id
    ).eq("action_type", action_type).gte("window_start", today_start).execute()

    if existing.data:
        row = existing.data[0]
        db.table("rate_limits").update({
            "request_count": row["request_count"] + 1,
        }).eq("id", row["id"]).execute()
    else:
        db.table("rate_limits").insert({
            "user_id": user_id,
            "action_type": action_type,
            "window_start": today_start,
            "request_count": 1,
        }).execute()


# ═══════════════════════════════════════════════════════════
# PORTFOLIOS
# ═══════════════════════════════════════════════════════════

def save_portfolio(
    user_id: str,
    name: str,
    tickers: list,
    weights: Optional[dict] = None,
    settings: Optional[dict] = None,
) -> Optional[Dict]:
    """Save or update a portfolio."""
    db = get_supabase()
    result = db.table("portfolios").insert({
        "user_id": user_id,
        "name": name,
        "tickers": tickers,
        "weights": weights,
        "settings": settings or {},
    }).execute()
    return result.data[0] if result.data else None


def get_portfolios(user_id: str) -> List[Dict]:
    """List portfolios for a user."""
    db = get_supabase()
    result = db.table("portfolios").select("*").eq(
        "user_id", user_id
    ).order("updated_at", desc=True).execute()
    return result.data or []


def update_portfolio(
    portfolio_id: str,
    user_id: str,
    **kwargs,
) -> Optional[Dict]:
    """Update a portfolio."""
    db = get_supabase()
    allowed = {"name", "tickers", "weights", "settings"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = db.table("portfolios").update(updates).eq(
        "id", portfolio_id
    ).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def delete_portfolio(portfolio_id: str, user_id: str) -> bool:
    """Delete a portfolio."""
    db = get_supabase()
    result = db.table("portfolios").delete().eq(
        "id", portfolio_id
    ).eq("user_id", user_id).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════
# WATCHLISTS
# ═══════════════════════════════════════════════════════════

def save_watchlist(user_id: str, name: str, tickers: list) -> Optional[Dict]:
    """Save a watchlist."""
    db = get_supabase()
    result = db.table("watchlists").insert({
        "user_id": user_id,
        "name": name,
        "tickers": tickers,
    }).execute()
    return result.data[0] if result.data else None


def get_watchlists(user_id: str) -> List[Dict]:
    """List watchlists for a user."""
    db = get_supabase()
    result = db.table("watchlists").select("*").eq(
        "user_id", user_id
    ).order("updated_at", desc=True).execute()
    return result.data or []


def update_watchlist(
    watchlist_id: str, user_id: str, tickers: list
) -> Optional[Dict]:
    """Update watchlist tickers."""
    db = get_supabase()
    result = db.table("watchlists").update({
        "tickers": tickers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", watchlist_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def delete_watchlist(watchlist_id: str, user_id: str) -> bool:
    """Delete a watchlist."""
    db = get_supabase()
    result = db.table("watchlists").delete().eq(
        "id", watchlist_id
    ).eq("user_id", user_id).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════
# USER API KEYS (encrypted storage)
# ═══════════════════════════════════════════════════════════

def save_user_api_key(user_id: str, provider: str, api_key: str) -> bool:
    """Save (upsert) an encrypted API key for a user."""
    db = get_supabase()
    encrypted = encrypt_api_key(api_key)
    now = datetime.now(timezone.utc).isoformat()

    # Check if exists
    existing = db.table("user_api_keys").select("id").eq(
        "user_id", user_id
    ).eq("provider", provider.lower()).execute()

    if existing.data:
        db.table("user_api_keys").update({
            "encrypted_key": encrypted,
            "updated_at": now,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("user_api_keys").insert({
            "user_id": user_id,
            "provider": provider.lower(),
            "encrypted_key": encrypted,
        }).execute()
    return True


def get_user_api_key(user_id: str, provider: str) -> Optional[str]:
    """Get decrypted API key for a user and provider."""
    db = get_supabase()
    result = db.table("user_api_keys").select("encrypted_key").eq(
        "user_id", user_id
    ).eq("provider", provider.lower()).execute()

    if not result.data:
        return None

    try:
        return decrypt_api_key(result.data[0]["encrypted_key"])
    except Exception:
        return None


def delete_user_api_key(user_id: str, provider: str) -> bool:
    """Delete a user's API key."""
    db = get_supabase()
    result = db.table("user_api_keys").delete().eq(
        "user_id", user_id
    ).eq("provider", provider.lower()).execute()
    return bool(result.data)


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _safe_serialize(obj: Any) -> Any:
    """
    Recursively make an object JSON-serializable.
    Handles pandas objects, numpy types, datetime, etc.
    """
    import numpy as np
    import pandas as pd

    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if not np.isnan(obj) else None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        return obj.to_dict()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    # Fallback: try str
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
