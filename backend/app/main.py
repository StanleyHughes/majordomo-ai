"""Majordomo token backend.

Hands the web client a short-lived LiveKit access token for a fresh room, and
asks LiveKit to send the Majordomo agent into that room. The browser never sees
the LiveKit API key or secret, or any model key (SEC-2).

Phase 2 replaces the hosted-mode access code with real sign-in.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel

from .config import Settings

log = logging.getLogger("majordomo.backend")

RATE_LIMIT_WINDOW = 60.0  # seconds
RATE_LIMIT_MAX = 10  # token requests per client per window


class TokenResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    expires_in: int


class _RateLimiter:
    """Small in-memory limiter. Good enough for one backend process."""

    def __init__(self, max_hits: int, window: float) -> None:
        self.max_hits = max_hits
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_hits:
            return False
        hits.append(now)
        return True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Majordomo backend", docs_url=None, redoc_url=None, openapi_url=None)
    limiter = _RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Access-Code"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def require_access(
        request: Request,
        x_access_code: str | None = Header(default=None),
    ) -> None:
        if not limiter.allow(client_key(request)):
            raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
        if not settings.hosted:
            return
        # SEC-4: hosted mode only serves tokens over HTTPS. The reverse proxy
        # (Caddy or Cloudflare Tunnel) terminates TLS and sets X-Forwarded-Proto.
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto != "https":
            raise HTTPException(403, "HTTPS is required.")
        if not x_access_code or not hmac.compare_digest(
            x_access_code.encode(), settings.access_code.encode()
        ):
            raise HTTPException(401, "That access code isn't right.")

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "mode": settings.mode,
            "livekit_configured": settings.livekit_configured,
            "access_code_required": settings.hosted,
        }

    @app.post("/api/token", response_model=TokenResponse, dependencies=[Depends(require_access)])
    def issue_token() -> TokenResponse:
        if not settings.livekit_configured:
            raise HTTPException(
                503,
                "LiveKit isn't set up yet. Add LIVEKIT_URL, LIVEKIT_API_KEY and "
                "LIVEKIT_API_SECRET to .env and restart.",
            )

        room_name = f"domo-{secrets.token_urlsafe(9)}"
        identity = f"user-{secrets.token_urlsafe(6)}"
        token = (
            api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(identity)
            .with_name("Guest" if settings.hosted else "Owner")
            .with_ttl(timedelta(seconds=settings.token_ttl_seconds))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    agents=[api.RoomAgentDispatch(agent_name=settings.agent_name)],
                    # Close the room soon after everyone leaves, so nothing idles.
                    empty_timeout=60,
                    departure_timeout=20,
                )
            )
            .to_jwt()
        )
        log.info("issued token room=%s identity=%s ttl=%ss", room_name, identity, settings.token_ttl_seconds)
        return TokenResponse(
            server_url=settings.livekit_url,
            participant_token=token,
            room_name=room_name,
            expires_in=settings.token_ttl_seconds,
        )

    return app
