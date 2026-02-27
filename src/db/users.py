"""
User CRUD operations — Supabase PostgreSQL.
"""

import bcrypt
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from src.db.connection import get_supabase


# ═══════════════════════════════════════════════════════════
# PASSWORD HASHING
# ═══════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════════

def create_user(
    email: str,
    password: str,
    name: str = "",
    role: str = "free",
    oauth_provider: Optional[str] = None,
    oauth_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a new user. Returns user dict or None if email exists."""
    db = get_supabase()

    # Check if email already exists
    existing = db.table("users").select("id").eq("email", email.lower()).execute()
    if existing.data:
        return None

    pw_hash = hash_password(password) if password else None

    result = db.table("users").insert({
        "email": email.lower().strip(),
        "password_hash": pw_hash,
        "name": name.strip(),
        "role": role,
        "oauth_provider": oauth_provider,
        "oauth_id": oauth_id,
    }).execute()

    return result.data[0] if result.data else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetch user by email."""
    db = get_supabase()
    result = db.table("users").select("*").eq("email", email.lower()).execute()
    return result.data[0] if result.data else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user by ID."""
    db = get_supabase()
    result = db.table("users").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else None


def update_user(user_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update user fields. Allowed: name, role, is_active."""
    db = get_supabase()
    allowed = {"name", "role", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = db.table("users").update(updates).eq("id", user_id).execute()
    return result.data[0] if result.data else None


def update_last_login(user_id: str):
    """Update the last_login timestamp."""
    db = get_supabase()
    db.table("users").update({
        "last_login": datetime.now(timezone.utc).isoformat()
    }).eq("id", user_id).execute()


def change_password(user_id: str, new_password: str) -> bool:
    """Change a user's password."""
    db = get_supabase()
    pw_hash = hash_password(new_password)
    result = db.table("users").update({
        "password_hash": pw_hash,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user_id).execute()
    return bool(result.data)


def list_users(role: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """List users (admin). Optionally filter by role."""
    db = get_supabase()
    query = db.table("users").select(
        "id, email, name, role, is_active, created_at, last_login"
    ).order("created_at", desc=True).limit(limit)
    if role:
        query = query.eq("role", role)
    result = query.execute()
    return result.data or []


def deactivate_user(user_id: str) -> bool:
    """Deactivate a user account."""
    result = update_user(user_id, is_active=False)
    return result is not None


def activate_user(user_id: str) -> bool:
    """Activate a user account."""
    result = update_user(user_id, is_active=True)
    return result is not None


# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

def create_session(
    user_id: str,
    ip_address: str = "",
    user_agent: str = "",
    ttl_hours: int = 24,
) -> str:
    """Create a new session. Returns session token."""
    db = get_supabase()
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    db.table("sessions").insert({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at.isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }).execute()

    return token


def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate a session token. Returns user dict if valid."""
    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    result = db.table("sessions").select(
        "user_id, expires_at"
    ).eq("token", token).gte("expires_at", now).execute()

    if not result.data:
        return None

    user_id = result.data[0]["user_id"]
    return get_user_by_id(user_id)


def delete_session(token: str):
    """Delete (invalidate) a session."""
    db = get_supabase()
    db.table("sessions").delete().eq("token", token).execute()


def delete_user_sessions(user_id: str):
    """Delete all sessions for a user (force logout)."""
    db = get_supabase()
    db.table("sessions").delete().eq("user_id", user_id).execute()


def cleanup_expired_sessions():
    """Remove expired sessions from the database."""
    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    db.table("sessions").delete().lt("expires_at", now).execute()


# ═══════════════════════════════════════════════════════════
# FAILED LOGIN TRACKING
# ═══════════════════════════════════════════════════════════

def record_failed_login(email: str, ip_address: str = ""):
    """Record a failed login attempt."""
    db = get_supabase()
    db.table("failed_logins").insert({
        "email": email.lower(),
        "ip_address": ip_address,
    }).execute()


def get_recent_failed_logins(email: str, minutes: int = 15) -> int:
    """Count failed login attempts in the last N minutes."""
    db = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    result = db.table("failed_logins").select(
        "id", count="exact"
    ).eq("email", email.lower()).gte("attempted_at", since).execute()
    return result.count or 0


def clear_failed_logins(email: str):
    """Clear failed login records for an email (after successful login)."""
    db = get_supabase()
    db.table("failed_logins").delete().eq("email", email.lower()).execute()


# ═══════════════════════════════════════════════════════════
# AUDIT LOGGING
# ═══════════════════════════════════════════════════════════

def log_audit(
    user_id: Optional[str],
    action: str,
    detail: str = "",
    ip_address: str = "",
):
    """Write an audit log entry."""
    db = get_supabase()
    db.table("audit_logs").insert({
        "user_id": user_id,
        "action": action,
        "detail": detail,
        "ip_address": ip_address,
    }).execute()


def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Fetch audit logs, optionally filtered."""
    db = get_supabase()
    query = db.table("audit_logs").select("*").order("created_at", desc=True).limit(limit)
    if user_id:
        query = query.eq("user_id", user_id)
    if action:
        query = query.eq("action", action)
    result = query.execute()
    return result.data or []
