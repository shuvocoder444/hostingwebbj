"""
Core Cache Utilities — Cache-Aside Pattern
==========================================
Implements Cache-Aside (Lazy Loading) caching with:
  - Consistent key namespacing
  - Type-safe generic helpers
  - Automatic cache invalidation hooks (used by signals)

Cache-Aside flow:
  1. Read from Redis → HIT → return
  2. MISS → query DB → write to Redis → return

Invalidation flow (via Django signals):
  post_save / post_delete → delete cache key → next request repopulates

All cache TTLs are centralised here for easy tuning.
"""

import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ─── TTL Constants (seconds) ─────────────────────────────────────────────────
# Tune these based on traffic patterns and data freshness requirements

TTL_CLIENT_DASHBOARD = 300        # 5 minutes: user-specific, changes on payment
TTL_HOSTING_PACKAGES = 600        # 10 minutes: rarely changes
TTL_SERVER_LIST = 120             # 2 minutes: servers go up/down
TTL_DOMAIN_PRICING = 900          # 15 minutes: pricing rarely changes
TTL_INVOICE_LIST = 180            # 3 minutes: new invoices arrive periodically
TTL_SHORT = 60                    # 1 minute: volatile data


# ─── Cache Key Builders ───────────────────────────────────────────────────────

def make_cache_key(*parts: Any) -> str:
    """
    Build a consistent, namespaced cache key from arbitrary parts.

    Example:
        make_cache_key('client_dashboard', user_id) → 'hostpro:client_dashboard:abc123'

    The 'hostpro:' prefix is also applied by KEY_PREFIX in settings,
    giving double-namespacing for safety in shared Redis environments.
    """
    parts_str = ":".join(str(p) for p in parts)
    return f"hostpro:{parts_str}"


def make_hashed_key(*parts: Any) -> str:
    """
    Hash-based cache key for long or complex parameters (e.g., query strings).
    Uses SHA-256 to produce a stable, fixed-length key.
    """
    raw = ":".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]  # 16 hex chars = 64 bits
    return f"hostpro:hashed:{digest}"


# ─── Cache-Aside Helper ───────────────────────────────────────────────────────

def cache_aside(
    key: str,
    loader: Callable[[], Any],
    ttl: int = 300,
    serializer: Optional[Callable] = None,
    deserializer: Optional[Callable] = None,
) -> Any:
    """
    Generic Cache-Aside implementation.

    Args:
        key:          Redis key to check/store under.
        loader:       Callable that fetches fresh data from DB (called on MISS).
        ttl:          Cache TTL in seconds.
        serializer:   Optional function to transform data before caching.
        deserializer: Optional function to restore data after cache read.

    Returns:
        Data from cache (HIT) or from loader (MISS).
    """
    # ── HIT ──────────────────────────────────────────────────────────────────
    cached = cache.get(key)
    if cached is not None:
        logger.debug("Cache HIT: %s", key)
        return deserializer(cached) if deserializer else cached

    # ── MISS ─────────────────────────────────────────────────────────────────
    logger.debug("Cache MISS: %s — loading from DB", key)
    data = loader()

    # Serialize if needed (e.g., convert queryset → list of dicts)
    to_store = serializer(data) if serializer else data
    cache.set(key, to_store, timeout=ttl)

    return data


def invalidate_cache(*keys: str) -> None:
    """
    Delete one or more cache keys.
    Called from Django signals on model save/delete.

    Args:
        *keys: One or more Redis keys to evict.
    """
    if keys:
        cache.delete_many(list(keys))
        logger.debug("Cache invalidated: %s", keys)


def invalidate_pattern(prefix: str) -> None:
    """
    Delete all keys matching a prefix pattern using Redis SCAN.
    Use sparingly — SCAN is O(N) across keyspace.

    Requires django-redis with DefaultClient.
    """
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        # Build full pattern including Django's KEY_PREFIX
        pattern = f"hostpro:{prefix}*"
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = conn.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                conn.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        logger.debug("Invalidated %d keys matching pattern '%s'", deleted, pattern)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pattern invalidation failed for '%s': %s", prefix, exc)


# ─── Decorator: per-view / per-function caching ───────────────────────────────

def cached_result(key_fn: Callable[..., str], ttl: int = 300):
    """
    Decorator that caches the return value of a function.

    Args:
        key_fn: A callable that receives the same args/kwargs as the decorated
                function and returns a cache key string.
        ttl:    Cache TTL in seconds.

    Usage:
        @cached_result(key_fn=lambda self: make_cache_key('pkg_list'), ttl=TTL_HOSTING_PACKAGES)
        def get_packages(self):
            return list(HostingPackage.objects.all().values())
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            cached = cache.get(key)
            if cached is not None:
                logger.debug("cached_result HIT: %s", key)
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result, timeout=ttl)
            return result
        return wrapper
    return decorator
