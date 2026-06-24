"""Fallback visibility notice (#51573).

The status-buffer pipeline does not reliably reach user-visible channels, so
fallback turns surface a notice by prepending it to the final response text.
These tests cover the detection helper (``_format_fallback_notice``) and the
turn_finalizer wiring that injects it.
"""

from unittest.mock import MagicMock

from run_agent import AIAgent

from agent.turn_finalizer import finalize_turn


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


# --- finalize_turn wiring -------------------------------------------------
#
# The streamed-Telegram bug (#51573): the notice mutates ``final_response``
# *after* the raw model text was already streamed.  The gateway only delivers
# that mutated text when the turn is flagged ``response_transformed=True`` —
# otherwise it suppresses the post-stream send and the notice never lands.
# These tests pin that the finalizer both injects the notice and raises the
# flag (and leaves it down when no fallback occurred).


def _finalizer_agent(*, model, provider):
    a = MagicMock()
    # Real fallback helper bound to this mock's runtime state.
    a._format_fallback_notice = lambda: AIAgent._format_fallback_notice(a)
    a._notify_on_fallback = True
    a._primary_runtime = {"model": "claude-opus-4-8", "provider": "anthropic"}
    a.model = model
    a.provider = provider
    # Keep the optional footers/explainers quiet so the only mutation under
    # test is the fallback notice.
    a._turn_failed_file_mutations = {}
    a._file_mutation_verifier_enabled.return_value = False
    a._turn_completion_explainer_enabled.return_value = False
    a.max_iterations = 90
    a.iteration_budget.remaining = 100
    a._tool_guardrail_halt_decision = None
    a._drain_pending_steer.return_value = None
    a._interrupt_message = None
    a._skill_nudge_interval = 0
    a.session_id = "sess-test"
    return a


def _finalize(agent, final_response):
    return finalize_turn(
        agent,
        final_response=final_response,
        api_call_count=1,
        interrupted=False,
        failed=False,
        messages=[{"role": "user", "content": "hi"}],
        conversation_history=[],
        effective_task_id=None,
        turn_id="turn-1",
        user_message="hi",
        original_user_message="hi",
        _should_review_memory=False,
        _turn_exit_reason="text_response",
    )


def test_finalizer_injects_notice_and_flags_transformed_on_fallback():
    a = _finalizer_agent(model="deepseek-v4-pro", provider="openrouter")
    result = _finalize(a, "quick test")
    assert result["final_response"].startswith("⚠️")
    assert "quick test" in result["final_response"]
    # The flag is what stops the gateway from suppressing the streamed final
    # send — without it the notice is dropped on Telegram.
    assert result["response_transformed"] is True


def test_finalizer_no_notice_and_not_transformed_without_fallback():
    a = _finalizer_agent(model="claude-opus-4-8", provider="anthropic")
    result = _finalize(a, "quick test")
    assert result["final_response"] == "quick test"
    assert result["response_transformed"] is False


def test_finalizer_disabled_does_not_force_transform():
    a = _finalizer_agent(model="deepseek-v4-pro", provider="openrouter")
    a._notify_on_fallback = False
    result = _finalize(a, "quick test")
    assert result["final_response"] == "quick test"
    assert result["response_transformed"] is False
