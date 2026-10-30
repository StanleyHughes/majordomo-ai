"""Backend settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

MIN_TTL = 60
MAX_TTL = 3600


class ConfigError(RuntimeError):
    """Raised when the configuration is unsafe or incomplete."""


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    mode: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    token_ttl_seconds: int
    access_code: str
    agent_name: str
    allowed_origins: list[str] = field(default_factory=list)

    @property
    def hosted(self) -> bool:
        return self.mode == "hosted"

    @property
    def livekit_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        mode = env.get("MAJORDOMO_MODE", "personal").strip().lower() or "personal"
        if mode not in ("personal", "hosted"):
            raise ConfigError(f"MAJORDOMO_MODE must be 'personal' or 'hosted', not {mode!r}")

        try:
            ttl = int(env.get("TOKEN_TTL_SECONDS", "600") or "600")
        except ValueError as exc:
            raise ConfigError("TOKEN_TTL_SECONDS must be a whole number of seconds") from exc
        ttl = max(MIN_TTL, min(MAX_TTL, ttl))

        settings = cls(
            mode=mode,
            livekit_url=env.get("LIVEKIT_URL", "").strip(),
            livekit_api_key=env.get("LIVEKIT_API_KEY", "").strip(),
            livekit_api_secret=env.get("LIVEKIT_API_SECRET", "").strip(),
            token_ttl_seconds=ttl,
            access_code=env.get("MAJORDOMO_ACCESS_CODE", "").strip(),
            agent_name=env.get("MAJORDOMO_AGENT_NAME", "majordomo").strip() or "majordomo",
            allowed_origins=_split(env.get("ALLOWED_ORIGINS", "")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Refuse to run hosted mode with unsafe settings (SEC-2, SEC-4)."""
        if not self.hosted:
            return
        problems = []
        if len(self.access_code) < 16:
            problems.append("MAJORDOMO_ACCESS_CODE must be set (16+ characters) in hosted mode")
        if self.livekit_url and not self.livekit_url.startswith("wss://"):
            problems.append("LIVEKIT_URL must use wss:// in hosted mode")
        for origin in self.allowed_origins:
            if not origin.startswith("https://"):
                problems.append(f"ALLOWED_ORIGINS entry {origin!r} must use https:// in hosted mode")
        if problems:
            raise ConfigError("; ".join(problems))
