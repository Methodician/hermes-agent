from unittest.mock import patch

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


TOPIC_CHAT_ID = "-100123"
TOPIC_THREAD_ID = "2503"
TOPIC_SESSION_KEY = "telegram-topic-session"


def _group_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=TOPIC_CHAT_ID,
        chat_type="group",
        thread_id=TOPIC_THREAD_ID,
        user_id="u1",
        user_name="Jake",
    )


def _make_runner(extra: dict):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(
                enabled=True,
                token="***",
                extra=extra,
            )
        }
    )
    runner.adapters = {}
    runner._session_model_overrides = {}
    runner._last_resolved_model = {}
    runner._normalize_source_for_session_key = lambda source: source
    runner._session_key_for_source = lambda source: TOPIC_SESSION_KEY
    return runner


def _topic_extra(**topic_overrides) -> dict:
    topic = {
        "name": "Identity Management",
        "thread_id": int(TOPIC_THREAD_ID),
        **topic_overrides,
    }
    return {
        "group_topics": [
            {
                "chat_id": TOPIC_CHAT_ID,
                "topics": [topic],
            }
        ]
    }


def test_topic_model_default_overrides_global_model_for_matching_topic():
    runner = _make_runner(_topic_extra(model="gpt-5.4"))

    with patch("gateway.run._resolve_gateway_model", return_value="deepseek/deepseek-v4-flash"), patch(
        "gateway.run._resolve_runtime_agent_kwargs",
        return_value={
            "provider": "openrouter",
            "api_key": "or-key",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
            "max_tokens": 4096,
        },
    ):
        model, kwargs = runner._resolve_session_agent_runtime(
            source=_group_source(),
            session_key=TOPIC_SESSION_KEY,
        )

    assert model == "gpt-5.4"
    assert kwargs["provider"] == "openrouter"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"


def test_topic_provider_default_replaces_runtime_bundle():
    runner = _make_runner(
        _topic_extra(
            model="gpt-5.4",
            provider="openai-codex",
        )
    )

    with patch("gateway.run._resolve_gateway_model", return_value="deepseek/deepseek-v4-flash"), patch(
        "gateway.run._resolve_runtime_agent_kwargs",
        return_value={
            "provider": "openrouter",
            "api_key": "or-key",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
            "max_tokens": 4096,
        },
    ), patch(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        return_value={
            "provider": "openai-codex",
            "api_key": "codex-key",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_mode": "codex_responses",
        },
    ):
        model, kwargs = runner._resolve_session_agent_runtime(
            source=_group_source(),
            session_key=TOPIC_SESSION_KEY,
        )

    assert model == "gpt-5.4"
    assert kwargs["provider"] == "openai-codex"
    assert kwargs["api_key"] == "codex-key"
    assert kwargs["base_url"] == "https://chatgpt.com/backend-api/codex"
    assert kwargs["api_mode"] == "codex_responses"


def test_session_model_override_still_beats_topic_default():
    runner = _make_runner(_topic_extra(model="gpt-5.4"))
    runner._session_model_overrides[TOPIC_SESSION_KEY] = {
        "model": "claude-sonnet-4",
        "provider": "anthropic",
        "api_key": "anth-key",
        "base_url": "https://api.anthropic.com",
        "api_mode": "anthropic_messages",
    }

    with patch("gateway.run._resolve_gateway_model", return_value="deepseek/deepseek-v4-flash"), patch(
        "gateway.run._resolve_runtime_agent_kwargs",
        return_value={
            "provider": "openrouter",
            "api_key": "or-key",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
            "max_tokens": 4096,
        },
    ):
        model, kwargs = runner._resolve_session_agent_runtime(
            source=_group_source(),
            session_key=TOPIC_SESSION_KEY,
        )

    assert model == "claude-sonnet-4"
    assert kwargs["provider"] == "anthropic"
    assert kwargs["api_key"] == "anth-key"


@pytest.mark.asyncio
async def test_model_command_uses_topic_default_as_current_model():
    runner = _make_runner(_topic_extra(model="gpt-5.4"))
    event = MessageEvent(text="/model", source=_group_source(), message_id="m1")

    with patch(
        "gateway.run._load_gateway_config",
        return_value={
            "model": {
                "default": "deepseek/deepseek-v4-flash",
                "provider": "openrouter",
            }
        },
    ), patch(
        "hermes_cli.model_switch.parse_model_flags",
        return_value=("", None, False, False),
    ), patch(
        "hermes_cli.model_switch.list_authenticated_providers",
        return_value=[],
    ):
        response = await runner._handle_model_command(event)

    assert isinstance(response, str)
    assert "gpt-5.4" in response
    assert "deepseek/deepseek-v4-flash" not in response
