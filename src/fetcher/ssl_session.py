"""
Shared SSL-safe session for yfinance.
In local/corporate environments, set DISABLE_SSL_VERIFY=1 in .env to bypass SSL.
On Streamlit Cloud, SSL works normally — no workaround needed.
"""

import ssl
import os
import urllib3

# ── SSL configuration ────────────────────────────────────
_DISABLE_SSL = os.environ.get("DISABLE_SSL_VERIFY", "0") == "1"

if _DISABLE_SSL:
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    os.environ["PYTHONHTTPSVERIFY"] = "0"


def get_session():
    """
    Create a requests-compatible session for yfinance.
    - When DISABLE_SSL_VERIFY=1: returns curl_cffi session with verify=False
    - Otherwise: returns None (yfinance 1.x manages its own curl_cffi session)
    """
    if not _DISABLE_SSL:
        # Let yfinance create its default session — most reliable on Cloud.
        return None

    # Local/corporate with SSL disabled: must provide custom session
    try:
        from curl_cffi.requests import Session as CurlSession
        return CurlSession(verify=False, impersonate="chrome")
    except Exception:
        pass

    # Last resort: standard requests (yfinance 1.x may reject, but try)
    import requests
    from requests.adapters import HTTPAdapter

    session = requests.Session()

    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

    session.verify = False
    adapter = SSLAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session
