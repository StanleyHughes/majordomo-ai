"""Agent settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_VOICE = "Charon"


@dataclass(frozen=True)
class AgentSettings:
    agent_name: str
    gemini_model: str
    gemini_voice: str
    user_address: str
    max_session_minutes: int
    persona_extra: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> AgentSettings:
        env = dict(os.environ if env is None else env)

        def get(name: str, default: str = "") -> str:
            return (env.get(name) or "").strip() or default

        try:
            max_minutes = int(get("MAJORDOMO_MAX_SESSION_MINUTES", "60"))
        except ValueError:
            max_minutes = 60

        return cls(
            agent_name=get("MAJORDOMO_AGENT_NAME", "majordomo"),
            gemini_model=get("GEMINI_MODEL", DEFAULT_MODEL),
            gemini_voice=get("GEMINI_VOICE", DEFAULT_VOICE),
            user_address=get("MAJORDOMO_USER_ADDRESS"),
            max_session_minutes=max(1, max_minutes),
            persona_extra=get("MAJORDOMO_PERSONA_EXTRA"),
        )


def missing_keys(env: dict[str, str] | None = None) -> list[str]:
    env = dict(os.environ if env is None else env)
    needed = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GOOGLE_API_KEY"]
    return [name for name in needed if not (env.get(name) or "").strip()]
