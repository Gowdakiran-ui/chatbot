"""Piece 5 of the security/auth hardening task — ASGI-level request body size cap.

Belt and suspenders alongside serving/app.py's Pydantic `message` length check:
that check only runs *after* the full body has already been read off the wire and
JSON-decoded, so a genuinely huge or malformed payload still costs a full buffer
+ parse before being rejected. This middleware rejects it earlier, at the byte
stream itself, before FastAPI's request parsing ever runs.

Reads the body incrementally via request.stream() and aborts as soon as the
cumulative size crosses max_bytes, rather than buffering the whole (possibly
enormous) body first — matters if a client sends more bytes than a truthful (or
absent/lying) Content-Length header would suggest.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > self._max_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)

        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > self._max_bytes:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
            chunks.append(chunk)

        # Cache the body on the request so downstream .body()/.json() calls
        # (FastAPI's own request parsing) reuse these bytes instead of trying to
        # re-read the now-exhausted ASGI receive stream.
        request._body = b"".join(chunks)

        return await call_next(request)
