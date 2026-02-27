"""
Login / Signup UI and authentication logic for Streamlit.
Supports email/password and Google OAuth via Supabase Auth.
"""

import re
import streamlit as st
from typing import Optional, Dict
from urllib.parse import parse_qs, urlparse
from src.db.users import (
    create_user, get_user_by_email, verify_password,
    create_session, validate_session, delete_session,
    update_last_login, record_failed_login,
    get_recent_failed_logins, clear_failed_logins,
    log_audit,
)
from src.i18n import get_language


# ═══════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SESSION_COOKIE_KEY = "_sa_session_token"


# ═══════════════════════════════════════════════════════════
# PASSWORD POLICY
# ═══════════════════════════════════════════════════════════

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Requires: min 8 chars, at least 3 of: uppercase, lowercase, digit, special.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다." if get_language() == "ko" else "Password must be at least 8 characters."

    checks = [
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)),
    ]
    if sum(checks) < 3:
        msg = (
            "비밀번호에 대문자, 소문자, 숫자, 특수문자 중 3가지 이상을 포함해야 합니다."
            if get_language() == "ko" else
            "Password must contain at least 3 of: uppercase, lowercase, digit, special character."
        )
        return False, msg

    return True, ""


def validate_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


# ═══════════════════════════════════════════════════════════
# CORE AUTH FUNCTIONS
# ═══════════════════════════════════════════════════════════

def login(email: str, password: str) -> tuple[bool, str]:
    """
    Authenticate user with email/password.
    Returns (success, message).
    """
    email = email.strip().lower()

    # Check lockout
    failed_count = get_recent_failed_logins(email, LOCKOUT_MINUTES)
    if failed_count >= MAX_FAILED_ATTEMPTS:
        msg = (
            f"로그인 시도가 너무 많습니다. {LOCKOUT_MINUTES}분 후에 다시 시도해주세요."
            if get_language() == "ko" else
            f"Too many login attempts. Please try again in {LOCKOUT_MINUTES} minutes."
        )
        return False, msg

    user = get_user_by_email(email)
    if not user:
        record_failed_login(email)
        msg = "이메일 또는 비밀번호가 올바르지 않습니다." if get_language() == "ko" else "Invalid email or password."
        return False, msg

    if not user.get("is_active", True):
        msg = "비활성화된 계정입니다. 관리자에게 문의하세요." if get_language() == "ko" else "Account is deactivated. Contact admin."
        return False, msg

    if not user.get("password_hash"):
        msg = "이 계정은 Google 로그인만 가능합니다." if get_language() == "ko" else "This account uses Google sign-in only."
        return False, msg

    if not verify_password(password, user["password_hash"]):
        record_failed_login(email)
        msg = "이메일 또는 비밀번호가 올바르지 않습니다." if get_language() == "ko" else "Invalid email or password."
        return False, msg

    # Success — create session
    clear_failed_logins(email)
    token = create_session(user["id"])
    update_last_login(user["id"])
    log_audit(user["id"], "login", f"Email login: {email}")

    # Store in session state
    _set_session(user, token)

    msg = f"환영합니다, {user.get('name') or email}!" if get_language() == "ko" else f"Welcome, {user.get('name') or email}!"
    return True, msg


def signup(email: str, password: str, name: str = "") -> tuple[bool, str]:
    """
    Register a new user.
    Returns (success, message).
    """
    email = email.strip().lower()

    # Validate email format
    if not validate_email(email):
        msg = "올바른 이메일 형식이 아닙니다." if get_language() == "ko" else "Invalid email format."
        return False, msg

    # Validate password
    valid, pwd_msg = validate_password(password)
    if not valid:
        return False, pwd_msg

    # Create user
    user = create_user(email, password, name=name, role="free")
    if not user:
        msg = "이미 등록된 이메일입니다." if get_language() == "ko" else "Email already registered."
        return False, msg

    # Auto-login
    token = create_session(user["id"])
    update_last_login(user["id"])
    log_audit(user["id"], "signup", f"New user: {email}")

    _set_session(user, token)

    msg = "회원가입이 완료되었습니다!" if get_language() == "ko" else "Registration complete!"
    return True, msg


def logout():
    """Log out the current user."""
    token = st.session_state.get(SESSION_COOKIE_KEY)
    user = st.session_state.get("user")

    if token:
        delete_session(token)
    if user:
        log_audit(user.get("id"), "logout", f"User: {user.get('email')}")

    # Clear session state
    for key in [SESSION_COOKIE_KEY, "user", "authenticated"]:
        if key in st.session_state:
            del st.session_state[key]


def get_current_user() -> Optional[Dict]:
    """Get the currently authenticated user, or None."""
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return st.session_state["user"]

    # Try to restore from session token
    token = st.session_state.get(SESSION_COOKIE_KEY)
    if token:
        user = validate_session(token)
        if user and user.get("is_active", True):
            _set_session(user, token)
            return user
        else:
            # Token expired or user deactivated
            for key in [SESSION_COOKIE_KEY, "user", "authenticated"]:
                if key in st.session_state:
                    del st.session_state[key]

    return None


def _set_session(user: dict, token: str):
    """Store authentication state in Streamlit session."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "free"),
    }
    st.session_state[SESSION_COOKIE_KEY] = token


# ═══════════════════════════════════════════════════════════
# STREAMLIT UI — LOGIN / SIGNUP PAGE
# ═══════════════════════════════════════════════════════════

def render_auth_page():
    """
    Render the login/signup page. 
    Call this at the top of app.py. Returns True if authenticated.
    """
    # ── Handle OAuth callback (Google redirect back) ─────
    try:
        _handle_oauth_callback()
    except Exception:
        pass  # Never block page rendering

    user = get_current_user()
    if user:
        return True

    lang = get_language()

    st.markdown("""
    <style>
        .auth-container {
            max-width: 420px;
            margin: 40px auto;
            padding: 30px;
            border-radius: 12px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        .auth-header {
            text-align: center;
            margin-bottom: 20px;
        }
        .auth-header h1 {
            font-size: 28px;
            margin: 0;
        }
        .auth-header p {
            color: #666;
            font-size: 14px;
        }
    </style>
    """, unsafe_allow_html=True)

    _col1, col_center, _col3 = st.columns([1, 2, 1])

    with col_center:
        st.markdown("## 📊 Stock Analyzer")
        st.caption("Institutional-grade stock valuation platform")

        # Language toggle on auth page
        _lang_options = ["한국어", "English"]
        _lang_map = {"한국어": "ko", "English": "en"}
        _cur_label = "한국어" if lang == "ko" else "English"
        _sel = st.selectbox("🌐", _lang_options, index=_lang_options.index(_cur_label), key="_auth_lang")
        if _lang_map[_sel] != st.session_state.get("language", "ko"):
            st.session_state["language"] = _lang_map[_sel]
            st.rerun()

        # ── LOGIN SECTION ────────────────────────────────
        st.markdown(f"### {'🔐 로그인' if lang == 'ko' else '🔐 Login'}")

        with st.form("login_form", clear_on_submit=False):
            login_email = st.text_input(
                "이메일" if lang == "ko" else "Email",
                placeholder="user@example.com",
                key="login_email",
            )
            login_password = st.text_input(
                "비밀번호" if lang == "ko" else "Password",
                type="password",
                key="login_password",
            )
            login_submitted = st.form_submit_button(
                "🔐 로그인" if lang == "ko" else "🔐 Login",
                use_container_width=True,
                type="primary",
            )

            if login_submitted:
                if not login_email or not login_password:
                    st.error(
                        "이메일과 비밀번호를 입력해주세요."
                        if lang == "ko" else "Please enter email and password."
                    )
                else:
                    success, msg = login(login_email, login_password)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        # Google OAuth button
        st.markdown(
            "<p style='text-align:center; color:#888; font-size:12px;'>OR</p>",
            unsafe_allow_html=True,
        )
        if st.button(
            "🔵 Google로 로그인" if lang == "ko" else "🔵 Sign in with Google",
            use_container_width=True,
            key="google_login_btn",
        ):
            _handle_google_oauth()

        # ── SIGNUP SECTION ───────────────────────────────
        st.markdown("---")
        st.markdown(f"### {'📝 회원가입' if lang == 'ko' else '📝 Sign Up'}")

        with st.form("signup_form", clear_on_submit=False):
            signup_name = st.text_input(
                "이름 (선택)" if lang == "ko" else "Name (optional)",
                key="signup_name",
            )
            signup_email = st.text_input(
                "이메일" if lang == "ko" else "Email",
                placeholder="user@example.com",
                key="signup_email",
            )
            signup_password = st.text_input(
                "비밀번호" if lang == "ko" else "Password",
                type="password",
                key="signup_password",
                help=(
                    "8자 이상, 대/소/숫자/특수 중 3가지 포함"
                    if lang == "ko" else
                    "Min 8 chars, at least 3 of: upper/lower/digit/special"
                ),
            )
            signup_confirm = st.text_input(
                "비밀번호 확인" if lang == "ko" else "Confirm Password",
                type="password",
                key="signup_confirm",
            )
            signup_submitted = st.form_submit_button(
                "📝 회원가입" if lang == "ko" else "📝 Sign Up",
                use_container_width=True,
                type="primary",
            )

            if signup_submitted:
                if not signup_email or not signup_password:
                    st.error(
                        "이메일과 비밀번호를 입력해주세요."
                        if lang == "ko" else "Please enter email and password."
                    )
                elif signup_password != signup_confirm:
                    st.error(
                        "비밀번호가 일치하지 않습니다."
                        if lang == "ko" else "Passwords do not match."
                    )
                else:
                    success, msg = signup(signup_email, signup_password, signup_name)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    return False


def _handle_google_oauth():
    """
    Initiate Google OAuth via Supabase REST API (implicit flow).
    PKCE flow doesn't work with Streamlit because the code_verifier
    is lost when the browser navigates away to Google and back.
    Instead, we use implicit flow which returns access_token in URL fragment.
    """
    try:
        redirect_url = _get_redirect_url()
        supabase_url = ""
        try:
            supabase_url = st.secrets.get("SUPABASE_URL", "")
        except Exception:
            import os
            supabase_url = os.environ.get("SUPABASE_URL", "")

        if not supabase_url:
            _show_oauth_not_configured()
            return

        # Construct the OAuth URL directly (implicit flow)
        # This bypasses the SDK's PKCE flow entirely
        import urllib.parse
        params = urllib.parse.urlencode({
            "provider": "google",
            "redirect_to": redirect_url,
            "response_type": "token",  # Force implicit flow → returns #access_token
        })
        oauth_url = f"{supabase_url}/auth/v1/authorize?{params}"

        # Redirect user to Google via Supabase
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={oauth_url}">',
            unsafe_allow_html=True,
        )
        st.info(
            "Google 로그인 페이지로 이동합니다..."
            if get_language() == "ko" else
            "Redirecting to Google..."
        )
    except Exception as e:
        err_msg = str(e)
        if "not enabled" in err_msg.lower() or "unsupported provider" in err_msg.lower():
            _show_oauth_not_configured()
        else:
            st.warning(
                f"Google OAuth를 사용할 수 없습니다. 이메일/비밀번호로 로그인해주세요.\n\n{err_msg}"
                if get_language() == "ko" else
                f"Google OAuth unavailable. Please use email/password.\n\n{err_msg}"
            )


def _get_redirect_url() -> str:
    """Get the appropriate redirect URL for OAuth callback."""
    # 1) Check session state override
    custom = st.session_state.get("_oauth_redirect")
    if custom:
        return custom

    # 2) Try to detect from Streamlit's own URL (works in Cloud & local)
    try:
        from streamlit.web.server.server_util import get_url
        # Not reliable, fall through
    except Exception:
        pass

    # 3) Check secrets for explicit site URL
    try:
        site_url = st.secrets.get("SITE_URL", "")
        if site_url:
            return site_url
    except Exception:
        pass

    # 4) Default: localhost for local dev, Cloud URL for production
    import os
    if os.environ.get("STREAMLIT_SERVER_PORT"):
        port = os.environ["STREAMLIT_SERVER_PORT"]
        return f"http://localhost:{port}"

    return "http://localhost:8501"


def _process_oauth_token(access_token: str, supabase_url: str, supabase_key: str):
    """Process an OAuth access token: get user info from Supabase & create session."""
    import httpx

    resp = httpx.get(
        f"{supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": supabase_key,
        },
        verify=False,
        timeout=15.0,
    )

    if resp.status_code == 200:
        user_data = resp.json()
        email = user_data.get("email", "")
        metadata = user_data.get("user_metadata", {})
        name = metadata.get("full_name", "") or metadata.get("name", "")
        oauth_id = user_data.get("id", "")

        existing = get_user_by_email(email)
        if existing:
            user = existing
        else:
            user = create_user(
                email=email,
                password="",
                name=name,
                role="free",
                oauth_provider="google",
                oauth_id=oauth_id,
            )

        if user:
            token = create_session(user["id"])
            update_last_login(user["id"])
            log_audit(user["id"], "login", f"Google OAuth: {email}")
            _set_session(user, token)
        return True
    return False


def _handle_oauth_callback():
    """
    Handle the OAuth callback after Google login.
    
    Implicit flow: Supabase redirects back with #access_token=... in URL fragment.
    URL fragments are NOT sent to the server, so we use JavaScript to:
    1. Detect the fragment
    2. Redirect to ?access_token=... so Streamlit can read it via query_params
    
    Also handles ?code= (PKCE/authorization code flow) as fallback.
    """
    params = st.query_params

    # ── Handle ?code= (authorization code flow fallback) ──
    auth_code = params.get("code")
    if auth_code:
        if st.session_state.get("_oauth_code_processed") == auth_code:
            return
        try:
            import httpx
            supabase_url = ""
            supabase_key = ""
            try:
                supabase_url = st.secrets.get("SUPABASE_URL", "")
                supabase_key = st.secrets.get("SUPABASE_SERVICE_KEY", "")
            except Exception:
                import os
                supabase_url = os.environ.get("SUPABASE_URL", "")
                supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

            # Exchange authorization code for tokens
            resp = httpx.post(
                f"{supabase_url}/auth/v1/token?grant_type=authorization_code",
                json={"auth_code": auth_code},
                headers={"apikey": supabase_key, "Content-Type": "application/json"},
                verify=False,
                timeout=15.0,
            )

            if resp.status_code == 200:
                token_data = resp.json()
                access_token_from_code = token_data.get("access_token", "")
                if access_token_from_code:
                    _process_oauth_token(access_token_from_code, supabase_url, supabase_key)
                    st.session_state["_oauth_code_processed"] = auth_code
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.query_params.clear()
            else:
                # Code exchange failed, clear and continue
                st.query_params.clear()
        except Exception:
            st.query_params.clear()
        return

    # ── Process access_token from query params (implicit flow via JS) ──
    access_token = params.get("access_token")
    if access_token:
        # Already processed
        if st.session_state.get("_oauth_token_processed") == access_token:
            return

        try:
            import httpx
            supabase_url = ""
            supabase_key = ""
            try:
                supabase_url = st.secrets.get("SUPABASE_URL", "")
                supabase_key = st.secrets.get("SUPABASE_SERVICE_KEY", "")
            except Exception:
                import os
                supabase_url = os.environ.get("SUPABASE_URL", "")
                supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

            if _process_oauth_token(access_token, supabase_url, supabase_key):
                st.session_state["_oauth_token_processed"] = access_token
                st.query_params.clear()
                st.rerun()
            else:
                st.query_params.clear()

        except Exception as e:
            st.query_params.clear()
            st.warning(
                f"Google 로그인 처리 실패: {str(e)}"
                if get_language() == "ko" else
                f"Google login failed: {str(e)}"
            )
        return

    # ── Step 1: Inject JS to capture URL fragment ──
    # After Google OAuth implicit flow, Supabase redirects with
    #   http://localhost:8501/#access_token=xxx&token_type=bearer&...
    # URL fragments (#) are invisible to the server/Streamlit.
    # This JS runs in the main window, detects the fragment,
    # and converts it into a query param that Streamlit CAN read.
    st.markdown("""
    <script>
    (function() {
        // Try multiple ways to access the top-level URL hash
        var hash = '';
        try { hash = window.top.location.hash; } catch(e) {}
        if (!hash) { try { hash = window.parent.location.hash; } catch(e) {} }
        if (!hash) { hash = window.location.hash; }

        if (hash && hash.indexOf('access_token') !== -1) {
            var params = new URLSearchParams(hash.substring(1));
            var accessToken = params.get('access_token');
            if (accessToken) {
                // Build clean URL with access_token as query param
                var loc = window.top || window.parent || window;
                var base = loc.location.origin + loc.location.pathname;
                loc.location.replace(base + '?access_token=' + encodeURIComponent(accessToken));
            }
        }
    })();
    </script>
    """, unsafe_allow_html=True)


def _show_oauth_not_configured():
    """Show a helpful message when Google OAuth is not configured."""
    lang = get_language()
    if lang == "ko":
        st.info(
            "🔧 **Google 로그인 설정 필요**\n\n"
            "Supabase 대시보드에서 Google 프로바이더를 활성화해야 합니다:\n"
            "1. [Supabase Dashboard](https://supabase.com/dashboard) → Authentication → Providers → Google\n"
            "2. Google Cloud Console에서 OAuth Client ID/Secret 생성\n"
            "3. 활성화 후 이메일/비밀번호로 먼저 로그인하세요."
        )
    else:
        st.info(
            "🔧 **Google Sign-in Setup Required**\n\n"
            "Enable Google provider in Supabase Dashboard:\n"
            "1. [Supabase Dashboard](https://supabase.com/dashboard) → Authentication → Providers → Google\n"
            "2. Create OAuth Client ID/Secret in Google Cloud Console\n"
            "3. Use email/password login in the meantime."
        )


# ═══════════════════════════════════════════════════════════
# SIDEBAR USER INFO
# ═══════════════════════════════════════════════════════════

def render_user_sidebar():
    """Render user info and logout button in the sidebar."""
    user = get_current_user()
    if not user:
        return

    lang = get_language()
    role_labels = {
        "admin": "👑 Admin",
        "premium": "⭐ Premium",
        "free": "🆓 Free",
    }

    with st.sidebar:
        st.markdown("---")
        role_label = role_labels.get(user["role"], user["role"])
        display_name = user.get("name") or user["email"].split("@")[0]

        st.markdown(f"**{display_name}** {role_label}")
        st.caption(user["email"])

        if st.button(
            "🚪 로그아웃" if lang == "ko" else "🚪 Logout",
            key="logout_btn",
            use_container_width=True,
        ):
            logout()
            st.rerun()
