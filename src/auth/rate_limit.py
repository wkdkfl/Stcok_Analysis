"""
Rate limiting module — per-user request throttling.
Uses in-memory tracking (session_state) with DB fallback for persistence.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import streamlit as st
from src.i18n import get_language
from src.auth.permissions import get_user_role


# ═══════════════════════════════════════════════════════════
# RATE LIMIT DEFINITIONS (requests per minute)
# ═══════════════════════════════════════════════════════════

RATE_LIMITS = {
    "admin": {
        "analysis": None,         # unlimited
        "screener": None,
        "ai_report": None,
    },
    "premium": {
        "analysis": 20,           # 20 per minute
        "screener": 3,            # 3 per minute
        "ai_report": 5,           # 5 per minute
    },
    "free": {
        "analysis": 5,            # 5 per minute
        "screener": 1,            # 1 per minute
        "ai_report": 0,           # not allowed
    },
}

# Window size in seconds
RATE_WINDOW = 60  # 1 minute


def _get_rate_key(action: str) -> str:
    """Generate a session state key for rate tracking."""
    return f"_rate_{action}"


def _get_timestamps(action: str) -> list:
    """Get the list of request timestamps for an action."""
    key = _get_rate_key(action)
    if key not in st.session_state:
        st.session_state[key] = []
    return st.session_state[key]


def _clean_old_timestamps(timestamps: list) -> list:
    """Remove timestamps older than the rate window."""
    cutoff = time.time() - RATE_WINDOW
    return [t for t in timestamps if t > cutoff]


def check_rate_limit(action: str) -> tuple[bool, str]:
    """
    Check if the current user is within rate limits for an action.
    Returns (allowed, message).
    """
    role = get_user_role()
    limits = RATE_LIMITS.get(role, RATE_LIMITS["free"])
    limit = limits.get(action)
    lang = get_language()

    # Unlimited
    if limit is None:
        return True, ""

    # Not allowed at all
    if limit == 0:
        msg = (
            f"🔒 이 기능은 현재 등급에서 사용할 수 없습니다."
            if lang == "ko" else
            f"🔒 This feature is not available for your plan."
        )
        return False, msg

    # Check timestamps
    key = _get_rate_key(action)
    timestamps = _get_timestamps(action)
    timestamps = _clean_old_timestamps(timestamps)
    st.session_state[key] = timestamps

    if len(timestamps) >= limit:
        wait_seconds = int(RATE_WINDOW - (time.time() - timestamps[0]))
        if wait_seconds < 0:
            wait_seconds = 0
        msg = (
            f"⏳ 요청이 너무 빠릅니다. {wait_seconds}초 후에 다시 시도해주세요. "
            f"(분당 {limit}회 제한)"
            if lang == "ko" else
            f"⏳ Too many requests. Please wait {wait_seconds}s. "
            f"(Limit: {limit}/min)"
        )
        return False, msg

    return True, ""


def record_request(action: str):
    """Record a request timestamp for rate limiting."""
    key = _get_rate_key(action)
    timestamps = _get_timestamps(action)
    timestamps = _clean_old_timestamps(timestamps)
    timestamps.append(time.time())
    st.session_state[key] = timestamps


def require_rate_limit(action: str) -> bool:
    """
    Check rate limit and show error if exceeded.
    Returns True if request is allowed.
    """
    allowed, msg = check_rate_limit(action)
    if not allowed:
        st.error(msg)
        return False
    record_request(action)
    return True
