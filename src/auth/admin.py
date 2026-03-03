"""
Admin panel — user management, audit log viewer, system stats.
Only accessible to users with role='admin'.
"""

import streamlit as st
from typing import List, Dict
from src.db.users import (
    list_users, update_user, deactivate_user, activate_user,
    get_audit_logs, delete_user_sessions,
)
from src.auth.permissions import is_admin
from src.i18n import get_language


def render_admin_panel():
    """
    Render the admin management panel.
    Must be called only after confirming user is admin.
    """
    if not is_admin():
        st.error("🔒 Admin access required.")
        return

    lang = get_language()

    st.markdown("## 👑 " + ("관리자 패널" if lang == "ko" else "Admin Panel"))

    admin_tab1, admin_tab2, admin_tab3 = st.tabs([
        "👥 " + ("사용자 관리" if lang == "ko" else "User Management"),
        "📋 " + ("감사 로그" if lang == "ko" else "Audit Logs"),
        "📊 " + ("시스템 통계" if lang == "ko" else "System Stats"),
    ])

    with admin_tab1:
        _render_user_management(lang)

    with admin_tab2:
        _render_audit_logs(lang)

    with admin_tab3:
        _render_system_stats(lang)


def _render_user_management(lang: str):
    """User list with role management."""

    # Filter controls
    col1, col2 = st.columns([1, 2])
    with col1:
        role_filter = st.selectbox(
            "역할 필터" if lang == "ko" else "Role Filter",
            ["전체" if lang == "ko" else "All", "admin", "premium", "free"],
            key="admin_role_filter",
        )

    role_q = None if role_filter in ("전체", "All") else role_filter
    users = list_users(role=role_q, limit=200)

    if not users:
        st.info("사용자가 없습니다." if lang == "ko" else "No users found.")
        return

    st.markdown(f"**{'총' if lang == 'ko' else 'Total'}: {len(users)}**")

    # User table
    for user in users:
        _uid = user["id"]
        _email = user["email"]
        _name = user.get("name", "")
        _role = user.get("role", "free")
        _active = user.get("is_active", True)
        _last = user.get("last_login", "—")
        _created = user.get("created_at", "")[:10]

        role_emoji = {"admin": "👑", "premium": "⭐", "free": "🆓"}.get(_role, "")
        status_emoji = "✅" if _active else "🚫"

        with st.expander(f"{status_emoji} {role_emoji} {_email} ({_name or '—'})", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.caption(f"ID: {_uid[:8]}...")
                st.caption(f"{'가입' if lang == 'ko' else 'Joined'}: {_created}")
                st.caption(f"{'최종 접속' if lang == 'ko' else 'Last login'}: {_last or '—'}")

            with col2:
                new_role = st.selectbox(
                    "역할" if lang == "ko" else "Role",
                    ["admin", "premium", "free"],
                    index=["admin", "premium", "free"].index(_role),
                    key=f"role_{_uid}",
                )
                if new_role != _role:
                    if st.button(
                        "역할 변경" if lang == "ko" else "Change Role",
                        key=f"chg_{_uid}",
                    ):
                        update_user(_uid, role=new_role)
                        st.success(f"{_email} → {new_role}")
                        st.rerun()

            with col3:
                if _active:
                    if st.button(
                        "🚫 비활성화" if lang == "ko" else "🚫 Deactivate",
                        key=f"deact_{_uid}",
                    ):
                        deactivate_user(_uid)
                        delete_user_sessions(_uid)
                        st.success(f"{_email} deactivated")
                        st.rerun()
                else:
                    if st.button(
                        "✅ 활성화" if lang == "ko" else "✅ Activate",
                        key=f"act_{_uid}",
                    ):
                        activate_user(_uid)
                        st.success(f"{_email} activated")
                        st.rerun()


def _render_audit_logs(lang: str):
    """Display recent audit logs."""

    col1, col2 = st.columns(2)
    with col1:
        action_filter = st.selectbox(
            "액션" if lang == "ko" else "Action",
            [
                "전체" if lang == "ko" else "All",
                "login", "logout", "signup",
                "analysis", "report", "admin_action",
            ],
            key="admin_audit_action",
        )
    with col2:
        log_limit = st.slider(
            "표시 건수" if lang == "ko" else "Show entries",
            10, 200, 50, 10,
            key="admin_audit_limit",
        )

    action_q = None if action_filter in ("전체", "All") else action_filter
    logs = get_audit_logs(action=action_q, limit=log_limit)

    if not logs:
        st.info("로그가 없습니다." if lang == "ko" else "No logs found.")
        return

    import pandas as pd
    df = pd.DataFrame(logs)
    display_cols = ["created_at", "action", "detail", "user_id", "ip_address"]
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available_cols],
        use_container_width=True,
        hide_index=True,
    )


def _render_system_stats(lang: str):
    """Show system statistics."""
    try:
        users = list_users(limit=10000)

        total = len(users)
        by_role = {}
        for u in users:
            r = u.get("role", "free")
            by_role[r] = by_role.get(r, 0) + 1

        active = sum(1 for u in users if u.get("is_active", True))
        inactive = total - active

        from src.mobile import is_mobile as _is_mobile_fn
        _admin_mobile = _is_mobile_fn()

        if _admin_mobile:
            c1, c2 = st.columns(2)
            c1.metric("👥 " + ("전체" if lang == "ko" else "Total"), total)
            c2.metric("👑 Admin", by_role.get("admin", 0))
            c3, c4 = st.columns(2)
            c3.metric("⭐ Premium", by_role.get("premium", 0))
            c4.metric("🆓 Free", by_role.get("free", 0))
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("👥 " + ("전체" if lang == "ko" else "Total"), total)
            col2.metric("👑 Admin", by_role.get("admin", 0))
            col3.metric("⭐ Premium", by_role.get("premium", 0))
            col4.metric("🆓 Free", by_role.get("free", 0))

        st.markdown("---")
        col1, col2 = st.columns(2)
        col1.metric("✅ " + ("활성" if lang == "ko" else "Active"), active)
        col2.metric("🚫 " + ("비활성" if lang == "ko" else "Inactive"), inactive)

    except Exception as e:
        st.error(f"통계 로드 실패: {e}" if lang == "ko" else f"Failed to load stats: {e}")
