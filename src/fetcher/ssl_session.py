"""
Shared SSL-safe session for yfinance.
Handles corporate proxy / firewall environments where SSL verification fails.
"""

import ssl
import os
import urllib3

# ── SSL workaround ───────────────────────────────────────
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
    Create a session with SSL verification disabled.
    Tries curl_cffi first (for yfinance >= 1.0), falls back to requests.
    """
    try:
        from curl_cffi.requests import Session as CurlSession
        session = CurlSession(verify=False, impersonate="chrome")
        return session
    except ImportError:
        pass

    # Fallback: standard requests with SSL adapter
    import requests
    from requests.adapters import HTTPAdapter

    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.verify = False
    adapter = SSLAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
