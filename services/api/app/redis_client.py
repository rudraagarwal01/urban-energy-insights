from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import redis

from app.config import get_settings


class StreamPublisher(Protocol):
    def xadd(self, name: str, fields: dict[str, str]) -> str: ...


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
