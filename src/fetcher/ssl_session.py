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
    Create a requests-compatible session.
    Uses curl_cffi if available (yfinance >= 1.0), else standard requests.
    SSL verification is disabled only when DISABLE_SSL_VERIFY=1.
    """
    try:
        from curl_cffi.requests import Session as CurlSession
        session = CurlSession(verify=not _DISABLE_SSL, impersonate="chrome")
        return session
    except ImportError:
        pass

    # Fallback: standard requests
    import requests
    from requests.adapters import HTTPAdapter

    session = requests.Session()

    if _DISABLE_SSL:
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                kwargs["ssl_context"] = ctx
                return super().init_poolmanager(*args, **kwargs)

        session.verify = False
        adapter = SSLAdapter()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    return session
