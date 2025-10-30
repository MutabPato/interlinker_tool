from __future__ import annotations

import time
from typing import Callable

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse

DEFAULT_THROTTLE_LIMIT = 100  # requests
DEFAULT_THROTTLE_WINDOW = 60  # seconds
DEFAULT_THROTTLE_KEY_PREFIX = 'interlinker:throttle'


class SlidingWindowRateThrottle:
    """Simple sliding-window rate limiter using the configured cache backend."""

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
        *,
        limit: int | None = None,
        window: int | None = None,
        cache_alias: str = 'default',
        key_prefix: str | None = None,
    ) -> None:
        self.get_response = get_response
        self.limit = limit or getattr(settings, 'THROTTLE_LIMIT', DEFAULT_THROTTLE_LIMIT)
        self.window = window or getattr(settings, 'THROTTLE_WINDOW', DEFAULT_THROTTLE_WINDOW)
        self.cache = caches[cache_alias]
        self.key_prefix = key_prefix or getattr(settings, 'THROTTLE_KEY_PREFIX', DEFAULT_THROTTLE_KEY_PREFIX)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method not in ('GET', 'POST'):
            return self.get_response(request)

        resolved = getattr(request, 'resolver_match', None)
        if resolved is None:
            return self.get_response(request)

        route_name = f"{resolved.namespace}:{resolved.url_name}" if resolved.namespace else resolved.url_name
        protected_routes = getattr(settings, 'THROTTLED_ROUTES', [])
        if route_name not in protected_routes:
            return self.get_response(request)

        cache_key = self._build_cache_key(request, route_name)
        now = time.time()
        bucket = self.cache.get(cache_key, [])
        bucket = [timestamp for timestamp in bucket if timestamp > now - self.window]

        if len(bucket) >= self.limit:
            return self._reject(request)

        bucket.append(now)
        self.cache.set(cache_key, bucket, timeout=self.window)
        return self.get_response(request)

    def _build_cache_key(self, request: HttpRequest, route_name: str) -> str:
        ip = self._get_client_ip(request)
        return f"{self.key_prefix}:{route_name}:{ip}"

    def _get_client_ip(self, request: HttpRequest) -> str:
        header = getattr(settings, 'THROTTLE_IP_HEADER', 'HTTP_X_FORWARDED_FOR')
        if header in request.META:
            value = request.META[header]
            return value.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _reject(self, request: HttpRequest) -> HttpResponse:
        from django.http import JsonResponse

        payload = {
            'detail': 'Rate limit exceeded. Try again shortly.',
            'route': getattr(request.resolver_match, 'view_name', 'unknown'),
        }
        return JsonResponse(payload, status=429)


def sliding_window_rate_throttle(get_response: Callable[[HttpRequest], HttpResponse]) -> SlidingWindowRateThrottle:
    return SlidingWindowRateThrottle(get_response)
