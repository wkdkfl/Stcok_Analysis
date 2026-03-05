"""
Mobile detection utility — detect viewport width via JS injection
and provide responsive layout helpers.
"""

import streamlit as st

try:
    import streamlit.components.v1 as components
except ImportError:
    components = None  # fallback: JS injection disabled

MOBILE_BREAKPOINT = 768  # px


def init_mobile_detect():
    """
    Inject JavaScript to detect viewport width once per session.
    Sets st.session_state["is_mobile"] = True/False.

    Flow:
      1st load  → inject JS → JS redirects with ?_vw=<width>
      2nd load  → read _vw, set is_mobile, mark _mobile_detected
      3rd+ load → immediate return (no query-param access)
    """
    # ── Fast path: already fully detected → skip everything ──
    if st.session_state.get("_mobile_detected"):
        return

    # ── Check _vw query param (set by JS redirect) ──
    params = st.query_params
    vw = params.get("_vw")
    if vw:
        try:
            st.session_state["is_mobile"] = int(vw) <= MOBILE_BREAKPOINT
        except (ValueError, TypeError):
            st.session_state["is_mobile"] = False
        # Mark detection as complete BEFORE touching query params
        st.session_state["_mobile_detected"] = True
        # Clean up the param so it doesn't show in URL
        try:
            del params["_vw"]
        except Exception:
            pass
        return

    # Already detected in a previous run (no _vw param present)
    if "is_mobile" in st.session_state:
        st.session_state["_mobile_detected"] = True
        return

    # First ever load — default to False until JS reports back
    st.session_state["is_mobile"] = False

    # Inject JS that redirects once with viewport width as query param
    if components:
        components.html(
            """
            <script>
            (function() {
                try {
                    const vw = window.innerWidth || document.documentElement.clientWidth;
                    const url = new URL(window.parent.location);
                    if (!url.searchParams.has('_vw')) {
                        url.searchParams.set('_vw', vw);
                        window.parent.location.replace(url.toString());
                    }
                } catch(e) { /* cross-origin or security error — ignored */ }
            })();
            </script>
            """,
            height=0,
            width=0,
        )


def is_mobile() -> bool:
    """Check if the current session is on a mobile device."""
    return st.session_state.get("is_mobile", False)


def auto_collapse_sidebar():
    """
    On mobile, automatically collapse the sidebar ONCE after login
    so the content area is fully visible. The user can reopen it
    via the floating toggle button (FAB).
    Only fires once per session to avoid fighting user actions.
    """
    if not is_mobile():
        return
    if st.session_state.get("_sidebar_auto_collapsed"):
        return  # already collapsed once this session
    st.session_state["_sidebar_auto_collapsed"] = True
    _inject_collapse_js()


def collapse_sidebar_now():
    """
    Collapse the sidebar on mobile after a user action (e.g. Analyze,
    Scan button click). Unlike auto_collapse_sidebar(), this fires
    every time it's called — guarded only by is_mobile().
    Also scrolls the main content to top for a smooth transition.
    """
    if not is_mobile():
        return
    # Check the flag set by on_click callbacks
    if not st.session_state.get("_collapse_after_action"):
        return
    st.session_state["_collapse_after_action"] = False
    _inject_collapse_js(scroll_top=True)


def _inject_collapse_js(scroll_top: bool = False):
    """Inject JS to click the sidebar collapse button."""
    extra_js = ""
    if scroll_top:
        extra_js = """
                // Scroll main content to top
                const main = window.parent.document.querySelector(
                    '[data-testid="stAppViewContainer"]'
                );
                if (main) { main.scrollTo({top: 0, behavior: 'smooth'}); }
        """
    if components:
        components.html(
            f"""
            <script>
            (function() {{
                const btn = window.parent.document.querySelector(
                    '[data-testid="stSidebarCollapseButton"] button'
                );
                if (btn) {{ btn.click(); }}
                {extra_js}
            }})();
            </script>
            """,
            height=0,
            width=0,
        )


def mcols(desktop: int, mobile: int = 1, gap: str = "small"):
    """
    Return st.columns() with responsive column count.
    On mobile, uses `mobile` columns. On desktop, uses `desktop` columns.
    """
    n = mobile if is_mobile() else desktop
    return st.columns(n, gap=gap)


def mcols_ratio(desktop_ratio: list, mobile_ratio: list = None, gap: str = "small"):
    """
    Return st.columns() with responsive ratios.
    If mobile_ratio is None, uses single column on mobile.
    """
    if is_mobile():
        ratio = mobile_ratio if mobile_ratio else [1]
    else:
        ratio = desktop_ratio
    return st.columns(ratio, gap=gap)


def render_metrics_grid(metrics: list, desktop_cols: int = 4, mobile_cols: int = 2):
    """
    Render a grid of st.metric() items responsively.
    metrics: list of (label, value) or (label, value, delta) tuples.
    """
    n = mobile_cols if is_mobile() else desktop_cols
    for row_start in range(0, len(metrics), n):
        chunk = metrics[row_start:row_start + n]
        cols = st.columns(len(chunk), gap="small")
        for col, item in zip(cols, chunk):
            with col:
                if len(item) == 2:
                    st.metric(item[0], item[1])
                elif len(item) == 3:
                    st.metric(item[0], item[1], delta=item[2])
                else:
                    st.metric(item[0], item[1])
