"""
Role-based permissions for 3-tier access control.
Roles: admin, premium, free
"""

import streamlit as st
from typing import Optional, Dict
from src.i18n import get_language


# ═══════════════════════════════════════════════════════════
# PERMISSION DEFINITIONS
# ═══════════════════════════════════════════════════════════

# Feature limits per role
ROLE_LIMITS = {
    "admin": {
        "max_tickers_per_analysis": 10,
        "screener_results_limit": None,       # unlimited
        "ai_reports_per_day": None,            # unlimited
        "portfolio_enabled": True,
        "backtest_enabled": True,
        "guru_full_access": True,
        "save_analyses_max": None,             # unlimited
        "can_input_api_key": True,
        "can_manage_users": True,
        "analysis_per_minute": None,           # unlimited
        "analysis_per_day": None,              # unlimited
        "screener_per_day": None,              # unlimited
    },
    "premium": {
        "max_tickers_per_analysis": 10,
        "screener_results_limit": None,        # full results
        "ai_reports_per_day": 5,
        "portfolio_enabled": True,
        "backtest_enabled": True,
        "guru_full_access": True,
        "save_analyses_max": 30,
        "can_input_api_key": True,
        "can_manage_users": False,
        "analysis_per_minute": 20,
        "analysis_per_day": None,              # unlimited
        "screener_per_day": None,              # unlimited
    },
    "free": {
        "max_tickers_per_analysis": 1,
        "screener_results_limit": 10,
        "ai_reports_per_day": 0,
        "portfolio_enabled": False,
        "backtest_enabled": False,
        "guru_full_access": False,
        "save_analyses_max": 0,
        "can_input_api_key": False,
        "can_manage_users": False,
        "analysis_per_minute": 5,
        "analysis_per_day": 10,               # 10 analyses per day
        "screener_per_day": 3,                # 3 screener scans per day
    },
}


def get_user_role() -> str:
    """Get the current user's role."""
    user = st.session_state.get("user")
    if user:
        return user.get("role", "free")
    return "free"


def get_limit(feature: str) -> any:
    """Get the limit for a feature based on the current user's role."""
    role = get_user_role()
    limits = ROLE_LIMITS.get(role, ROLE_LIMITS["free"])
    return limits.get(feature)


def check_permission(feature: str) -> bool:
    """
    Check if the current user has permission for a feature.
    Returns True if allowed, False if denied.
    """
    limit = get_limit(feature)
    if limit is None:  # unlimited
        return True
    if isinstance(limit, bool):
        return limit
    if isinstance(limit, int):
        return limit > 0
    return True


def require_permission(feature: str, show_upgrade: bool = True) -> bool:
    """
    Check permission and optionally show upgrade message.
    Returns True if allowed.
    """
    if check_permission(feature):
        return True

    if show_upgrade:
        _show_upgrade_message(feature)
    return False


def require_role(min_role: str) -> bool:
    """
    Check if user has at least the specified role.
    Hierarchy: admin > premium > free
    """
    hierarchy = {"free": 0, "premium": 1, "admin": 2}
    user_role = get_user_role()
    return hierarchy.get(user_role, 0) >= hierarchy.get(min_role, 0)


# ═══════════════════════════════════════════════════════════
# UPGRADE MESSAGE
# ═══════════════════════════════════════════════════════════

def _show_upgrade_message(feature: str):
    """Show an upgrade prompt when a feature is restricted."""
    lang = get_language()
    role = get_user_role()

    feature_names = {
        "portfolio_enabled": "포트폴리오 시뮬레이션" if lang == "ko" else "Portfolio Simulation",
        "backtest_enabled": "백테스트" if lang == "ko" else "Backtest",
        "ai_reports_per_day": "AI 리포트" if lang == "ko" else "AI Reports",
        "can_input_api_key": "API 키 입력" if lang == "ko" else "API Key Input",
        "guru_full_access": "13F 구루 전체 접근" if lang == "ko" else "13F Guru Full Access",
        "save_analyses_max": "분석 저장" if lang == "ko" else "Save Analysis",
        "can_manage_users": "사용자 관리" if lang == "ko" else "User Management",
    }

    feature_name = feature_names.get(feature, feature)

    if role == "free":
        if lang == "ko":
            st.warning(
                f"🔒 **{feature_name}**은(는) Premium 이상 등급에서 사용 가능합니다.\n\n"
                f"관리자에게 등급 업그레이드를 요청하세요."
            )
        else:
            st.warning(
                f"🔒 **{feature_name}** requires Premium or higher.\n\n"
                f"Contact your admin for an upgrade."
            )
    elif role == "premium":
        if lang == "ko":
            st.warning(f"🔒 **{feature_name}**은(는) Admin 전용 기능입니다.")
        else:
            st.warning(f"🔒 **{feature_name}** is Admin-only.")


# ═══════════════════════════════════════════════════════════
# CONVENIENCE CHECKERS
# ═══════════════════════════════════════════════════════════

def can_use_portfolio() -> bool:
    """Check if user can access portfolio features."""
    return check_permission("portfolio_enabled")


def can_use_backtest() -> bool:
    """Check if user can access backtest features."""
    return check_permission("backtest_enabled")


def can_generate_ai_report() -> bool:
    """Check if user can generate AI reports (has quota remaining)."""
    limit = get_limit("ai_reports_per_day")
    if limit is None:
        return True
    if limit == 0:
        return False
    # Check actual count
    try:
        from src.db.data import count_daily_reports
        user = st.session_state.get("user", {})
        if not user.get("id"):
            return False
        used = count_daily_reports(user["id"])
        return used < limit
    except Exception:
        return limit > 0


def get_ai_report_quota() -> tuple[int, Optional[int]]:
    """Returns (used_today, daily_limit). Limit is None for unlimited."""
    limit = get_limit("ai_reports_per_day")
    try:
        from src.db.data import count_daily_reports
        user = st.session_state.get("user", {})
        if user.get("id"):
            used = count_daily_reports(user["id"])
        else:
            used = 0
    except Exception:
        used = 0
    return used, limit


def get_max_tickers() -> int:
    """Get max tickers for analysis."""
    return get_limit("max_tickers_per_analysis") or 1


def get_screener_limit() -> Optional[int]:
    """Get screener results limit (None = unlimited)."""
    return get_limit("screener_results_limit")


def can_save_analysis() -> bool:
    """Check if user can save more analyses."""
    limit = get_limit("save_analyses_max")
    if limit is None:
        return True
    if limit == 0:
        return False
    try:
        from src.db.data import count_saved_analyses
        user = st.session_state.get("user", {})
        if not user.get("id"):
            return False
        count = count_saved_analyses(user["id"])
        return count < limit
    except Exception:
        return limit > 0


def is_admin() -> bool:
    """Check if current user is admin."""
    return get_user_role() == "admin"


# ═══════════════════════════════════════════════════════════
# DAILY USAGE LIMITS
# ═══════════════════════════════════════════════════════════

def check_daily_limit(action: str) -> bool:
    """
    Check if the current user is within the daily limit for an action.
    action should be 'analysis' or 'screener' (maps to '{action}_per_day' key).
    Returns True if allowed.
    """
    limit = get_limit(f"{action}_per_day")
    if limit is None:
        return True
    if limit == 0:
        return False

    try:
        from src.db.data import count_daily_usage
        user = st.session_state.get("user", {})
        if not user.get("id"):
            return True  # no user context, allow (rate_limit will catch)
        used = count_daily_usage(user["id"], action)
        return used < limit
    except Exception:
        return True  # on DB error, allow (fail-open)


def get_daily_usage(action: str) -> tuple:
    """
    Returns (used_today, daily_limit) for a given action.
    Limit is None for unlimited.
    """
    limit = get_limit(f"{action}_per_day")
    try:
        from src.db.data import count_daily_usage
        user = st.session_state.get("user", {})
        if user.get("id"):
            used = count_daily_usage(user["id"], action)
        else:
            used = 0
    except Exception:
        used = 0
    return used, limit


def require_daily_limit(action: str) -> bool:
    """
    Check daily limit and show warning if exceeded.
    Returns True if request is allowed.
    """
    if check_daily_limit(action):
        return True

    lang = get_language()
    limit = get_limit(f"{action}_per_day")

    action_names = {
        "analysis": "종목 분석" if lang == "ko" else "Stock Analysis",
        "screener": "스크리너" if lang == "ko" else "Screener",
    }
    action_name = action_names.get(action, action)

    if lang == "ko":
        st.warning(
            f"🔒 오늘 **{action_name}** 사용 한도({limit}회)를 초과했습니다.\n\n"
            f"내일 다시 시도하거나 **Premium**으로 업그레이드하세요."
        )
    else:
        st.warning(
            f"🔒 You've reached today's **{action_name}** limit ({limit} uses).\n\n"
            f"Try again tomorrow or upgrade to **Premium**."
        )
    return False


def record_usage(action: str):
    """Record a daily usage for the current user."""
    try:
        from src.db.data import record_daily_usage
        user = st.session_state.get("user", {})
        if user.get("id"):
            record_daily_usage(user["id"], action)
    except Exception:
        pass
