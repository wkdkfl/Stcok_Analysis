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
    """Inject JS to click the sidebar collapse button and optionally scroll to top.

    Uses multi-fallback selectors for Streamlit version compatibility
    and a MutationObserver fallback if the button isn't rendered yet.
    """
    scroll_js = ""
    if scroll_top:
        scroll_js = """
                // Scroll every possible container to top
                var scrollTargets = [
                    doc.querySelector('[data-testid="stAppViewContainer"]'),
                    doc.querySelector('[data-testid="stMain"]'),
                    doc.querySelector('[data-testid="stMainBlockContainer"]'),
                    doc.querySelector('[data-testid="stVerticalBlock"]'),
                    doc.querySelector('section.main'),
                ];
                for (var i = 0; i < scrollTargets.length; i++) {
                    if (scrollTargets[i]) { scrollTargets[i].scrollTop = 0; }
                }
                window.parent.scrollTo(0, 0);
                doc.documentElement.scrollTop = 0;
        """
    if components:
        components.html(
            f"""
            <script>
            (function() {{
                var doc = window.parent.document;

                // Multi-fallback selectors for sidebar collapse button
                var SELECTORS = [
                    '[data-testid="stSidebarCollapseButton"] button',
                    '[data-testid="collapsedControl"] button',
                    'button[aria-label="Close sidebar"]',
                    'button[aria-label="Close sidebar navigation"]',
                    'section[data-testid="stSidebar"] button[kind="header"]',
                ];

                function findCollapseBtn() {{
                    for (var i = 0; i < SELECTORS.length; i++) {{
                        var btn = doc.querySelector(SELECTORS[i]);
                        if (btn) return btn;
                    }}
                    return null;
                }}

                function doCollapse() {{
                    var btn = findCollapseBtn();
                    if (btn) {{
                        btn.click();
                        {scroll_js}
                        return true;
                    }}
                    return false;
                }}

                // Attempt after 300ms (most common case)
                setTimeout(function() {{
                    if (doCollapse()) return;

                    // Fallback: MutationObserver waits up to 3s for the button
                    if (typeof MutationObserver !== 'undefined') {{
                        var observer = new MutationObserver(function(mutations, obs) {{
                            if (doCollapse()) {{ obs.disconnect(); }}
                        }});
                        observer.observe(doc.body, {{ childList: true, subtree: true }});
                        setTimeout(function() {{ observer.disconnect(); }}, 3000);
                    }}
                }}, 300);
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


def render_mobile_bottom_nav(tab_keys: list, tab_labels: list, active_tab: str,
                             nav_icons: dict, nav_labels_short: dict, lang: str = "ko"):
    """
    Render a fixed bottom navigation bar on mobile devices.

    Uses components.html() to inject the nav into the parent document's DOM,
    bypassing Streamlit's HTML sanitizer (which strips onclick handlers).
    Also visually hides the st.radio nav widget so only the bottom bar is shown.

    Parameters
    ----------
    tab_keys : list[str]        e.g. ["analysis", "screener", "guru", ...]
    tab_labels : list[str]      Translated radio labels (used to identify the radio widget)
    active_tab : str            Currently active tab key
    nav_icons : dict            key → emoji icon
    nav_labels_short : dict     key → {lang: label}
    lang : str                  Current UI language
    """
    if not components or not is_mobile():
        return

    # Build nav items HTML (no onclick — event listeners added via JS)
    items_html = ""
    for i, key in enumerate(tab_keys):
        active_cls = "active" if key == active_tab else ""
        icon = nav_icons.get(key, "📄")
        lbl = nav_labels_short.get(key, {}).get(lang, key)
        items_html += (
            f'<div class="nav-item {active_cls}" data-idx="{i}">'
            f'<span class="nav-icon">{icon}</span>'
            f'<span class="nav-label">{lbl}</span>'
            f'</div>'
        )

    # Escape backticks in items_html to be safe inside JS template literal
    items_html_escaped = items_html.replace("`", "\\`")

    # JSON encode tab labels for safe JS string matching
    import json
    tab_labels_js = json.dumps(tab_labels, ensure_ascii=False)

    components.html(
        f"""
        <script>
        (function() {{
            const parent = window.parent.document;
            const TAB_LABELS = {tab_labels_js};

            // ── Remove existing nav (avoid duplicates on rerun) ──
            const existing = parent.querySelector('.mobile-bottom-nav');
            if (existing) existing.remove();

            // ── Find the correct radio widget (main_nav_radio) ──
            // Match by comparing label texts against our known tab labels
            function findNavRadio() {{
                const allRadios = parent.querySelectorAll('[data-testid="stRadio"]');
                for (const radio of allRadios) {{
                    const labels = radio.querySelectorAll('[role="radiogroup"] label');
                    if (labels.length === TAB_LABELS.length) {{
                        const firstText = labels[0] ? labels[0].textContent.trim() : '';
                        if (firstText === TAB_LABELS[0]) {{
                            return {{ widget: radio, labels: labels }};
                        }}
                    }}
                }}
                return null;
            }}

            // ── Create & append bottom nav ──
            const nav = document.createElement('div');
            nav.className = 'mobile-bottom-nav';
            nav.innerHTML = `{items_html_escaped}`;
            parent.body.appendChild(nav);

            // ── Click handlers ──
            nav.querySelectorAll('.nav-item').forEach(function(item) {{
                item.addEventListener('click', function() {{
                    const idx = parseInt(this.getAttribute('data-idx'));
                    const found = findNavRadio();
                    if (found && found.labels[idx]) {{
                        // Temporarily make radio visible so click dispatches
                        const container = found.widget.closest(
                            '[data-testid="stElementContainer"]'
                        ) || found.widget.parentElement;
                        if (container) {{
                            const prevStyle = container.style.cssText;
                            container.style.cssText = 'position:absolute!important;opacity:0!important;pointer-events:auto!important;';
                            found.labels[idx].click();
                            // Re-hide after click propagates
                            requestAnimationFrame(function() {{
                                container.style.cssText = prevStyle;
                            }});
                        }} else {{
                            found.labels[idx].click();
                        }}
                    }}
                    // Scroll main content to top
                    const main = parent.querySelector('[data-testid="stAppViewContainer"]');
                    if (main) main.scrollTo({{ top: 0, behavior: 'smooth' }});
                }});
            }});

            // ── Hide the main nav radio widget (keep functional) ──
            const navRadio = findNavRadio();
            if (navRadio) {{
                const container = navRadio.widget.closest(
                    '[data-testid="stElementContainer"]'
                ) || navRadio.widget.parentElement;
                if (container) {{
                    container.style.cssText = 'position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;pointer-events:none!important;border:0!important;';
                }}
            }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


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
