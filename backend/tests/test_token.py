import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from app.main import create_app

KEY = "APItestkey"
SECRET = "test-secret-that-is-long-enough-for-hs256-signing"
CODE = "a-very-long-access-code-1234"


def make_settings(**overrides) -> Settings:
    env = {
        "MAJORDOMO_MODE": "personal",
        "LIVEKIT_URL": "wss://example.livekit.cloud",
        "LIVEKIT_API_KEY": KEY,
        "LIVEKIT_API_SECRET": SECRET,
        "TOKEN_TTL_SECONDS": "600",
    }
    env.update(overrides)
    return Settings.from_env(env)


def decode(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False})


def test_personal_mode_issues_short_lived_room_scoped_token():
    client = TestClient(create_app(make_settings()))
    resp = client.post("/api/token")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_url"] == "wss://example.livekit.cloud"
    claims = decode(body["participant_token"])
    assert claims["exp"] - claims["nbf"] == 600
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["room"] == body["room_name"]
    assert claims["roomConfig"]["agents"][0]["agentName"] == "majordomo"


def test_response_never_contains_secrets():
    client = TestClient(create_app(make_settings()))
    text = client.post("/api/token").text + client.get("/api/health").text
    assert SECRET not in text
    assert KEY not in text.replace(f'"iss":"{KEY}"', "")  # only inside the signed JWT


def test_each_token_gets_a_fresh_room():
    client = TestClient(create_app(make_settings()))
    rooms = {client.post("/api/token").json()["room_name"] for _ in range(3)}
    assert len(rooms) == 3


def test_ttl_is_clamped():
    assert make_settings(TOKEN_TTL_SECONDS="999999").token_ttl_seconds == 3600
    assert make_settings(TOKEN_TTL_SECONDS="1").token_ttl_seconds == 60


def test_missing_livekit_config_gives_plain_error():
    client = TestClient(create_app(make_settings(LIVEKIT_URL="")))
    resp = client.post("/api/token")
    assert resp.status_code == 503
    assert "LIVEKIT_URL" in resp.json()["detail"]


def test_hosted_mode_requires_access_code_setting():
    with pytest.raises(ConfigError):
        make_settings(MAJORDOMO_MODE="hosted")


def test_hosted_mode_requires_wss():
    with pytest.raises(ConfigError):
        make_settings(MAJORDOMO_MODE="hosted", MAJORDOMO_ACCESS_CODE=CODE, LIVEKIT_URL="ws://x")


def test_hosted_mode_rejects_plain_http():
    client = TestClient(create_app(make_settings(MAJORDOMO_MODE="hosted", MAJORDOMO_ACCESS_CODE=CODE)))
    resp = client.post("/api/token", headers={"X-Access-Code": CODE, "X-Forwarded-Proto": "http"})
    assert resp.status_code == 403


def test_hosted_mode_checks_access_code():
    client = TestClient(create_app(make_settings(MAJORDOMO_MODE="hosted", MAJORDOMO_ACCESS_CODE=CODE)))
    https = {"X-Forwarded-Proto": "https"}
    assert client.post("/api/token", headers=https).status_code == 401
    assert client.post("/api/token", headers={**https, "X-Access-Code": "wrong"}).status_code == 401
    ok = client.post("/api/token", headers={**https, "X-Access-Code": CODE})
    assert ok.status_code == 200


def test_rate_limit():
    client = TestClient(create_app(make_settings()))
    codes = [client.post("/api/token").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10
    assert codes[-1] == 429
