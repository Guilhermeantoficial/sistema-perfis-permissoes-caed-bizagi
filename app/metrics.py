from __future__ import annotations

import re
import time

from prometheus_client import Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_REQUESTS = Counter(
    "caed_http_requests_total",
    "Total de requisições HTTP.",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "caed_http_request_duration_seconds",
    "Duração das requisições HTTP.",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
INTEGRATION_RESULTS = Counter(
    "caed_integration_jobs_total",
    "Resultado dos jobs de integração.",
    ["provider", "event", "result"],
)

_NUMERIC_SEGMENT = re.compile(r"/\d+(?=/|$)")
_UUID_SEGMENT = re.compile(r"/[0-9a-fA-F-]{32,36}(?=/|$)")


def normalized_path(path: str) -> str:
    value = _UUID_SEGMENT.sub("/{id}", path)
    return _NUMERIC_SEGMENT.sub("/{id}", value)


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = normalized_path(scope.get("path", "/"))
        status = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
            HTTP_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)
