"""
Retry decorator — automatic retry with exponential backoff for network calls.
Only retries transient errors (connection, timeout, HTTP 5xx/429).
"""

import time
import functools
import logging
from typing import Tuple, Type

logger = logging.getLogger(__name__)

# Exception types that warrant a retry
_RETRYABLE_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import requests
    _RETRYABLE_EXCEPTIONS = _RETRYABLE_EXCEPTIONS + (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
    )
except ImportError:
    pass


def with_retry(max_retries: int = 2, backoff: float = 1.0, retryable: tuple = None):
    """
    Decorator that retries a function on transient network errors.

    Parameters
    ----------
    max_retries : int
        Number of retries after first failure (default 2 → 3 total attempts).
    backoff : float
        Base delay between retries in seconds. Doubles each retry.
    retryable : tuple of exception types
        Override which exceptions to retry on.
    """
    retry_on = retryable or _RETRYABLE_EXCEPTIONS

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_retries:
                        wait = backoff * (2 ** attempt)
                        logger.debug(
                            f"Retry {attempt + 1}/{max_retries} for {fn.__name__}: "
                            f"{type(e).__name__}. Waiting {wait:.1f}s"
                        )
                        time.sleep(wait)
                except Exception:
                    raise  # non-retryable → fail immediately
            raise last_exc  # all retries exhausted
        return wrapper
    return decorator
