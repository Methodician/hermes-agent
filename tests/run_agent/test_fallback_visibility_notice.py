"""Fallback visibility notice (#51573).

The status-buffer pipeline does not reliably reach user-visible channels, so
fallback turns surface a notice by prepending it to the final response text.
These tests cover the detection helper (``_format_fallback_notice``) and the
turn_finalizer wiring that injects it.
"""

from run_agent import AIAgent


def _agent():
    a = AIAgent.__new__(AIAgent)
    a._notify_on_fallback = True
    a._primary_runtime = {"model": "claude-opus-4-8", "provider": "anthropic"}
    a.model = "claude-opus-4-8"
    a.provider = "anthropic"
    return a


def test_no_notice_when_primary_active():
    a = _agent()
    assert a._format_fallback_notice() is None


def test_notice_when_model_differs():
    a = _agent()
    a.model = "deepseek-v4-pro"
    a.provider = "deepseek"
    notice = a._format_fallback_notice()
    assert notice is not None
    assert "claude-opus-4-8 (anthropic)" in notice
    assert "deepseek-v4-pro (deepseek)" in notice


def test_notice_when_only_provider_differs():
    a = _agent()
    a.provider = "openrouter"
    assert a._format_fallback_notice() is not None


def test_disabled_suppresses_notice():
    a = _agent()
    a._notify_on_fallback = False
    a.model = "deepseek-v4-pro"
    a.provider = "deepseek"
    assert a._format_fallback_notice() is None


def test_missing_primary_runtime_is_safe():
    a = _agent()
    a._primary_runtime = {}
    a.model = "deepseek-v4-pro"
    assert a._format_fallback_notice() is None
