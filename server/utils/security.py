import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "code",
    "password",
    "passwd",
    "pwd",
    "session",
}

SENSITIVE_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token|token|password|passwd|pwd|session)\b"
    r"([\"'\s:=]+)([^\s\"'&,]+)"
)


def mask_sensitive_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    return SENSITIVE_KEY_VALUE_PATTERN.sub(r"\1\2[REDACTED]", text)


def mask_sensitive_url(url: str) -> str:
    if not url:
        return ""

    try:
        parts = urlsplit(url)
        query_items = _mask_query_pairs(parse_qsl(parts.query, keep_blank_values=True))
        fragment_items = _mask_query_pairs(parse_qsl(parts.fragment, keep_blank_values=True))
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query_items, doseq=True),
                urlencode(fragment_items, doseq=True),
            )
        )
    except Exception:
        return mask_sensitive_text(url)


def _mask_query_pairs(items: Iterable[Tuple[str, str]]) -> list[Tuple[str, str]]:
    masked = []
    for key, value in items:
        if key.lower() in SENSITIVE_QUERY_KEYS:
            masked.append((key, "[REDACTED]"))
        else:
            masked.append((key, value))
    return masked


def get_client_ip(request) -> str:
    for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
        raw_value = request.headers.get(header)
        if not raw_value:
            continue
        first_value = raw_value.split(",")[0].strip()
        if first_value:
            return first_value

    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return host or "unknown"


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_sec: int) -> Tuple[bool, int]:
        if limit <= 0 or window_sec <= 0:
            return True, 0

        now = time.monotonic()
        with self._lock:
            bucket = self._events[key]
            cutoff = now - window_sec
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(window_sec - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

