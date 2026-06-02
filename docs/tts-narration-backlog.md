# TTS Narration Backlog

This backlog tracks local refinements for the long-form `/voice narrate` prototype before extracting a clean upstream PR from current `upstream/main`.

## P0 — Required before upstream extraction

1. **Port onto a clean `upstream/main` worktree**
   - Current live implementation is proven locally, but `gateway/run.py` and `gateway/platforms/base.py` are too divergent for a direct PR.
   - Manually transplant only narration-specific hunks onto a fresh branch from `upstream/main`.
   - Acceptance: no unrelated deletions in `gateway/run.py` / `gateway/platforms/base.py`; `tests/gateway` collects successfully.

2. **Preserve upstream TTS provider flexibility**
   - Replace hardcoded long-form defaults with config-driven behavior that can inherit the normal `tts.provider` path or use an explicit long-form override.
   - Proposed config shape:
     - `tts.long_form.provider` or `voice.long_form_tts.primary_provider`
     - optional `model`, `voice`, chunk policy, and fallback behavior
   - Acceptance: Edge/default TTS still works; custom command providers work; OpenRouter/Coral route can be selected without code changes.

3. **Wire model/voice metadata or remove unused fields**
   - The job store currently records provider/model/voice, but processing only passes `provider` into `text_to_speech_tool`.
   - Acceptance: either model/voice influence generation via supported provider options, or fields are clearly future-only and not user-facing.

4. **Fix retention/privacy behavior for completed chunk text**
   - Module comment says full private text only lives while retryable; completed chunks currently keep text indefinitely.
   - Acceptance: completed jobs redact chunk text, prune via TTL, or docs/config explicitly describe retention.

5. **Run upstream-compatible test gate**
   - Required targeted checks:
     - `tests/gateway/test_tts_narration.py`
     - `tests/gateway/test_post_delivery_callback_chaining.py`
     - `tests/gateway/test_voice_command.py`
     - `tests/gateway/test_planned_stop_watcher.py`
   - Required broader check: full `tests/gateway` collection/pass or documented upstream baseline failures only.

## P1 — Should finish before opening a PR

1. **Config and docs for long-form narration**
   - Document `/voice narrate`, `/voice narrate chat`, `/voice off`, status behavior, topic-vs-chat scope, and provider selection.
   - Add slash-command help text/i18n strings instead of hardcoded English where upstream conventions expect translations.

2. **Retry/resume operator UX**
   - Add a safe command or log workflow to inspect failed narration jobs and retry them without duplicating already-sent chunks.
   - Acceptance: failed chunk/job can be retried idempotently and reports sanitized error text.

3. **Provider fallback behavior**
   - Decide whether long-form narration should fail closed on configured provider failure or fall back to global/default TTS.
   - Acceptance: behavior is explicit in config/tests; no silent surprise provider switch for private voice output.

4. **Backpressure/concurrency guard**
   - Avoid multiple long narration jobs for the same topic running over each other.
   - Acceptance: jobs are serialized per scope or clear status is reported when one is already processing.

5. **Cross-platform behavior audit**
   - Telegram is validated. Check Discord/Signal/base adapter assumptions around `send_voice`, captions, reply anchors, and callback timing.
   - Acceptance: unsupported platforms fail cleanly; supported platforms preserve metadata/threading.

## P2 — Nice-to-have local polish

1. **Chunking quality tuning**
   - Make target/max chars configurable per provider.
   - Add tests for Markdown/code/media-heavy responses and paragraph rhythm.

2. **Observability**
   - Add concise logs/metrics for enqueue, chunk synth, send, failure, retry, completion.
   - Keep private text out of logs.

3. **Status command detail**
   - `/voice status` could show effective scope and long-form provider in use.

4. **Cleanup job**
   - Periodically purge completed narration artifacts and stale temp audio files.

5. **PR decomposition**
   - Consider separate PRs if upstream review load is high:
     - async post-delivery callback support
     - TTS provider override plumbing
     - long-form narration mode/store
