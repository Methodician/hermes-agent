from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from plugins.personal_comms_bridge import register, tools


class FakeContext:
    def __init__(self):
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path == "/health":
            return {"ok": True, "service": "personal-comms-bridge", "side_effects_enabled": False}
        if path == "/connectors":
            return {"connectors": [{"name": "gmail", "read_only": True}]}
        if path.endswith("/status"):
            return {"source": "gmail", "ok": True, "auth_state": "ready", "read_only": True}
        if path.endswith("/recent") or path == "/attention/recent" or path.endswith("/attention"):
            return {"items": []}
        raise AssertionError(path)


def decode(result: str) -> dict:
    return json.loads(result)


def test_register_exposes_one_read_only_tool():
    ctx = FakeContext()

    register(ctx)

    assert len(ctx.tools) == 1
    registered = ctx.tools[0]
    assert registered["name"] == "personal_comms_bridge"
    assert registered["toolset"] == "personal_comms_bridge"
    assert registered["schema"]["parameters"]["properties"]["action"]["enum"] == [
        "health",
        "connectors",
        "connector_status",
        "recent",
        "attention",
        "connector_attention",
    ]


def test_health_action_uses_bridge_health(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(tools, "_client_from_args", lambda args: fake)

    payload = decode(tools.handle_personal_comms_bridge({"action": "health"}))

    assert payload["success"] is True
    assert payload["bridge"]["service"] == "personal-comms-bridge"
    assert payload["bridge"]["side_effects_enabled"] is False
    assert fake.calls == [("/health", None)]


def test_recent_action_clamps_limit_and_uses_connector_endpoint(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(tools, "_client_from_args", lambda args: fake)

    payload = decode(
        tools.handle_personal_comms_bridge(
            {"action": "recent", "connector": "google_messages", "limit": 999}
        )
    )

    assert payload["success"] is True
    assert payload["connector"] == "google_messages"
    assert payload["limit"] == 100
    assert fake.calls == [("/connectors/google_messages/recent", {"limit": 100})]


def test_attention_action_does_not_require_connector(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(tools, "_client_from_args", lambda args: fake)

    payload = decode(tools.handle_personal_comms_bridge({"action": "attention", "limit": 5}))

    assert payload["success"] is True
    assert payload["limit"] == 5
    assert fake.calls == [("/attention/recent", {"limit": 5})]


def test_connector_name_validation_rejects_path_traversal(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(tools, "_client_from_args", lambda args: fake)

    payload = decode(
        tools.handle_personal_comms_bridge(
            {"action": "connector_status", "connector": "../gmail"}
        )
    )

    assert payload["success"] is False
    assert "connector must contain only" in payload["error"]
    assert fake.calls == []


def test_base_url_must_be_loopback():
    with pytest.raises(tools.CommsBridgeConfigError, match="localhost/loopback"):
        tools._validate_loopback_url("https://example.com:8765")


def test_http_error_is_reported_as_json(monkeypatch):
    def fake_urlopen(req, timeout):
        raise HTTPError(
            req.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(tools, "urlopen", fake_urlopen)
    client = tools.BridgeClient()

    with pytest.raises(tools.CommsBridgeHTTPError) as excinfo:
        client.get("/connectors/nope/status")

    assert excinfo.value.status_code == 404
    assert "HTTP 404" in str(excinfo.value)


def test_check_available_returns_true_for_safe_local_default(monkeypatch):
    monkeypatch.delenv(tools.BRIDGE_URL_ENV, raising=False)

    assert tools.check_personal_comms_bridge_available() is True


def test_check_available_returns_false_for_nonlocal_url(monkeypatch):
    monkeypatch.setenv(tools.BRIDGE_URL_ENV, "https://example.com:8765")

    assert tools.check_personal_comms_bridge_available() is False
