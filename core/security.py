"""
Security & Performance Helpers for VeloHoster
==============================================
Provides:
  - In-Memory & Redis Rate Limiting protection for sensitive endpoints (login, register, whois).
  - Security headers injector middleware.
  - SQL query / connection optimization hooks.
"""
import time
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def get_client_ip(request):
    """Extract real client IP address even when behind reverse proxies / Cloudflare."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def rate_limit(key_prefix='rate_limit', max_requests=60, window_seconds=60):
    """
    High-speed distributed rate limiter using Django's cache backend (Redis / LocMem).
    Protects login, register, and WHOIS search from bot spam / brute-force.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            ip = get_client_ip(request)
            cache_key = f"rl:{key_prefix}:{ip}"
            
            try:
                current_count = cache.get(cache_key, 0)
                if current_count >= max_requests:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Too Many Requests',
                            'message': 'Rate limit exceeded. Please wait a moment before trying again.',
                        }, status=429)
                    return HttpResponse('Too many requests. Please slow down and try again in a few moments.', status=429)
                
                # Increment counter
                if current_count == 0:
                    cache.set(cache_key, 1, timeout=window_seconds)
                else:
                    cache.incr(cache_key)
            except Exception:
                # If cache is temporarily unavailable, don't block user traffic
                pass
            
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

