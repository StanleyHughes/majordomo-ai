from majordomo_agent.config import DEFAULT_MODEL, AgentSettings, missing_keys
from majordomo_agent.persona import build_instructions, greeting_instructions


def test_persona_is_majordomo_and_dry():
    text = build_instructions()
    assert "Majordomo" in text and "Domo" in text
    assert "dry" in text.lower()


def test_address_by_name_or_title():
    assert '"Stan"' in build_instructions("Stan")
    assert '"Sir"' in build_instructions("Sir")
    assert "Stan" in greeting_instructions("Stan")


def test_no_address():
    text = build_instructions("")
    assert "Do not address the user by name or title" in text
    assert '"' not in greeting_instructions("")


def test_extra_persona_text_is_appended():
    assert build_instructions(None, "Prefers metric units.").endswith("Prefers metric units.")


def test_settings_defaults():
    s = AgentSettings.from_env({})
    assert s.gemini_model == DEFAULT_MODEL
    assert s.gemini_voice == "Charon"
    assert s.agent_name == "majordomo"
    assert s.max_session_minutes == 60


def test_settings_from_env():
    s = AgentSettings.from_env(
        {"GEMINI_VOICE": "Puck", "MAJORDOMO_USER_ADDRESS": "Doctor", "MAJORDOMO_MAX_SESSION_MINUTES": "5"}
    )
    assert (s.gemini_voice, s.user_address, s.max_session_minutes) == ("Puck", "Doctor", 5)


def test_missing_keys():
    assert set(missing_keys({})) == {"LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GOOGLE_API_KEY"}
    full = {k: "x" for k in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GOOGLE_API_KEY"]}
    assert missing_keys(full) == []
