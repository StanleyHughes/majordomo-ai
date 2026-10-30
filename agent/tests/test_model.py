from majordomo_agent.config import AgentSettings
from majordomo_agent.main import build_model


def test_gemini_live_has_resumption_and_compression(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = build_model(AgentSettings.from_env({}))
    opts = model._opts
    assert opts.session_resumption is not None
    assert opts.context_window_compression.sliding_window is not None
    assert opts.voice == "Charon"
    vad = opts.realtime_input_config.automatic_activity_detection
    assert vad.silence_duration_ms == 600
    assert vad.disabled is not True
