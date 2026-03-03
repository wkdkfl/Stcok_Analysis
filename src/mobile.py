"""
Mobile detection utility — detect viewport width via JS injection
and provide responsive layout helpers.
"""

import streamlit as st
import streamlit.components.v1 as components

MOBILE_BREAKPOINT = 768  # px


def init_mobile_detect():
    """
    Inject JavaScript to detect viewport width once per session.
    Sets st.session_state["is_mobile"] = True/False.
    """
    # Always check query params first (handles redirect callback)
    params = st.query_params
    vw = params.get("_vw")
    if vw:
        try:
            st.session_state["is_mobile"] = int(vw) <= MOBILE_BREAKPOINT
        except (ValueError, TypeError):
            if "is_mobile" not in st.session_state:
                st.session_state["is_mobile"] = False
        # Clean up the param so it doesn't show in URL
        try:
            del params["_vw"]
        except Exception:
            pass
        return

    # Already detected in a previous run (no _vw param present)
    if "is_mobile" in st.session_state:
        return

    # First ever load — default to False until JS reports back
    st.session_state["is_mobile"] = False

    # Inject JS that redirects once with viewport width as query param
    components.html(
        """
        <script>
        (function() {
            const vw = window.innerWidth || document.documentElement.clientWidth;
            const url = new URL(window.parent.location);
            if (!url.searchParams.has('_vw')) {
                url.searchParams.set('_vw', vw);
                window.parent.location.replace(url.toString());
            }
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
    components.html(
        """
        <script>
        (function() {
            const btn = window.parent.document.querySelector(
                '[data-testid="stSidebarCollapseButton"] button'
            );
            if (btn) { btn.click(); }
        })();
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
