from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def moscow_now() -> datetime:
    return datetime.now(MOSCOW_TZ)
