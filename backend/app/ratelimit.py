"""Per-visitor hourly limits for the calls that spend Gnani credits (recall clips, live listening sessions).
In memory, per process: enough for one Render instance; resets on redeploy."""
from __future__ import annotations

import time
from collections import defaultdict, deque

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def allow(bucket: str, key: str, per_hour: int) -> bool:
    q, now = _hits[(bucket, key)], time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= per_hour:
        return False
    q.append(now)
    return True


def reset() -> None:
    _hits.clear()
