# OpenRouter setup and smoke-test runbook for The Tower

Purpose: configure OpenRouter as a Hermes model provider after Jake supplies an API key, without leaking secrets, changing the live default route prematurely, or restarting the Telegram gateway without approval.

This runbook is intentionally operator-facing. It separates Jake-owned embodied/account steps from Glow-owned Tower steps, because the key boundary is consent and custody: Jake owns the OpenRouter account and key; Glow can verify plumbing and run safe smoke tests once the key exists.

## Guardrails

- Do not print, paste into chat, board comments, logs, screenshots, or commit an API key.
- Do not fabricate a placeholder key and call it configured. Missing key means blocked, not “probably fine.”
- Do not restart the live Telegram gateway during setup or testing unless Jake explicitly approves it.
- Do not change `model.provider` / `model.default` globally until the key is present, one-off CLI smoke tests pass, and Jake chooses OpenRouter as the default route.
- Do not store secrets in repo files. `~/.hermes/.env` is the right place for API keys; repo-local docs and board comments are not.
- Prefer one-off `hermes chat --provider openrouter --model ...` tests before any persistent config change.

## Source facts checked

- OpenRouter provider ID: `openrouter`.
- Key env var: `OPENROUTER_API_KEY`, stored in `~/.hermes/.env`.
- Optional base URL override: `OPENROUTER_BASE_URL`.
- Default OpenRouter-specific config keys live under `openrouter:`:
  - `response_cache: true`
  - `response_cache_ttl: 300`
  - `min_coding_score: 0.65`
- OpenRouter is treated as an OpenAI-compatible aggregator provider in `hermes_cli/providers.py`.
- Hermes adds OpenRouter-specific attribution/cache headers automatically when the base URL host is `openrouter.ai`.
- Curated OpenRouter model suggestions are in `website/static/api/model-catalog.json`; the live picker can fetch/filter models beyond that snapshot.

## Jake-owned steps

1. Create or choose an OpenRouter account and billing posture.
   - Key page: https://openrouter.ai/keys
   - Set spend limits on the OpenRouter side before wiring the key into The Tower. Tiny brakes, fewer expensive surprises.

2. Generate an API key.
   - Copy it once into the place where it will be stored.
   - Do not paste it into Telegram, a kanban card, a shell transcript that will be shared, or a repo file.

3. Decide the initial test model class.
   - Cheap/fast smoke: a low-cost or free OpenRouter model from the live catalog.
   - Better Hermes/tool-call smoke: a known tool-capable general model, for example a Claude, Gemini, Qwen, Kimi, or OpenAI model exposed by OpenRouter.
   - Coding router experiment: `openrouter/pareto-code` after basic provider auth works.

4. Decide whether OpenRouter should become:
   - a one-off provider only,
   - an auxiliary/fallback provider,
   - or the main default model provider.

## Glow-owned Tower steps

Run these from the Tower shell. Do not echo the real key back to the terminal.

### 1. Inspect current routing before touching anything

```bash
cd /home/methodician/projects/hermes-agent
hermes config path
hermes config env-path
python - <<'PY'
from hermes_cli.config import load_config
cfg = load_config()
print('model:', cfg.get('model', {}))
print('fallback_model:', cfg.get('fallback_model', None))
print('openrouter:', cfg.get('openrouter', {}))
PY
```

Check only routing/config shape. Do not dump `~/.hermes/.env` if it may contain secrets.

### 2. Store the key in the profile env file

Preferred manual path when Jake is present:

```bash
${EDITOR:-nano} ~/.hermes/.env
```

Add exactly one line, replacing the placeholder locally in the editor:

```dotenv
OPENROUTER_API_KEY=<paste-key-here>
```

Then lock down permissions:

```bash
chmod 600 ~/.hermes/.env
```

Optional base URL override only if there is a specific reason:

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Usually omit `OPENROUTER_BASE_URL`; Hermes/provider metadata already knows the normal endpoint.

### 3. Verify key presence without printing it

```bash
python - <<'PY'
from pathlib import Path
p = Path.home() / '.hermes' / '.env'
found = False
for line in p.read_text().splitlines() if p.exists() else []:
    line = line.strip()
    if line.startswith('OPENROUTER_API_KEY=') and line.split('=', 1)[1].strip():
        found = True
        break
print('OPENROUTER_API_KEY:', 'present' if found else 'missing')
PY
```

If it says `missing`, stop and ask Jake to supply/store the key. Do not proceed with fake auth.

### 4. Verify Hermes recognizes the provider

```bash
python - <<'PY'
from hermes_cli.providers import get_provider
p = get_provider('openrouter')
print('provider:', p.id if p else 'missing')
print('transport:', p.transport if p else 'n/a')
print('aggregator:', p.is_aggregator if p else 'n/a')
print('key envs:', ','.join(p.api_key_env_vars) if p else 'n/a')
print('base_url:', p.base_url if p else 'n/a')
PY
```

Expected shape: provider `openrouter`, OpenAI-compatible chat transport, aggregator true, key envs including `OPENROUTER_API_KEY`, base URL resolving to OpenRouter or the configured override.

### 5. One-off no-tools smoke test

Pick a modest model from the live/OpenRouter catalog. The exact model can change over time, so if this fails with “model not found,” use `hermes model` or OpenRouter’s model list to pick a current tool-capable model.

```bash
hermes chat -Q \
  --provider openrouter \
  --model google/gemini-3-flash-preview \
  -q 'Reply with exactly: openrouter-ok'
```

Pass condition: the command returns `openrouter-ok` or a clearly successful equivalent, with no auth/routing error.

Common failure meanings:

- Missing/invalid key: fix `OPENROUTER_API_KEY` in `~/.hermes/.env`.
- Model unavailable: choose a different OpenRouter model ID.
- Provider/routing error: inspect `~/.hermes/logs/errors.log` carefully, redacting secrets before sharing.

### 6. Optional tool-call smoke test

Only run this after the no-tools smoke passes. Use a model expected to support tool calling.

```bash
hermes chat -Q \
  --provider openrouter \
  --model anthropic/claude-haiku-4.5 \
  --toolsets terminal \
  -q 'Use the terminal tool to run: printf openrouter-tool-ok. Then reply with only the printed text.'
```

Pass condition: Hermes performs a terminal tool call and returns `openrouter-tool-ok`.

If the model answers without using the tool, try another tool-capable model before blaming Hermes. OpenRouter models vary; the cheap one is not always the correct one.

### 7. Optional Pareto-code router test

`openrouter/pareto-code` uses `openrouter.min_coding_score` as the quality/cost threshold. The repo default is `0.65`.

```bash
hermes chat -Q \
  --provider openrouter \
  --model openrouter/pareto-code \
  -q 'In one sentence, explain what a token bucket rate limiter does.'
```

Adjust only if Jake wants to tune cost/quality:

```yaml
openrouter:
  min_coding_score: 0.65
```

Higher means stronger/more expensive coders; lower means cheaper/faster options. Empty string delegates routing to OpenRouter’s documented default.

## Persistent config options

Only apply these after successful one-off tests and an explicit decision.

### Make OpenRouter the main provider

```yaml
model:
  provider: openrouter
  default: google/gemini-3-flash-preview
```

`model.default` and `model.model` are aliases in Hermes config; prefer `default` for consistency with docs.

### Use OpenRouter as fallback only

```yaml
fallback_model:
  provider: openrouter
  model: anthropic/claude-sonnet-4.6
```

Fallbacks trigger on rate limits, overload/service errors, or connection failures. Keep this off until cost expectations are clear.

### Use OpenRouter for auxiliary tasks

Example for a cheaper auxiliary compression model:

```yaml
auxiliary:
  compression:
    provider: openrouter
    model: google/gemini-3-flash-preview
```

Auxiliary tasks are independent. Main-agent OpenRouter routing knobs such as `openrouter.min_coding_score` do not automatically propagate to auxiliary calls.

### OpenRouter response cache knobs

Defaults from the repo:

```yaml
openrouter:
  response_cache: true
  response_cache_ttl: 300
  min_coding_score: 0.65
```

Environment overrides:

```dotenv
HERMES_OPENROUTER_CACHE=true
HERMES_OPENROUTER_CACHE_TTL=300
```

Most operators should leave these alone at first.

## Gateway posture

A CLI smoke test does not require a Telegram gateway restart.

If and only if Jake decides OpenRouter should become the live Telegram/default route:

1. Patch `~/.hermes/config.yaml` deliberately.
2. Verify YAML parses.
3. Check gateway activity/logs first.
4. Ask Jake before restart.
5. Restart only at a safe moment.
6. Verify with a short Telegram test in a low-stakes topic.

No stealth restarts. The gateway may be carrying active work; don’t kick the ladder while someone is climbing it.

## Redaction checklist for board comments/logs

Safe to mention:

- `OPENROUTER_API_KEY` exists or is missing.
- Provider ID/model ID used.
- Command exit status.
- Error class after redaction: auth failed, model not found, 429, 503, etc.

Not safe to mention:

- Any actual key characters.
- Full `.env` contents.
- Raw request headers.
- Screenshots of OpenRouter account/key pages.
- Unredacted `~/.hermes/logs/*` excerpts if they include Authorization headers or request dumps.

## Minimal happy path

```bash
# Jake: create key at OpenRouter and paste it into ~/.hermes/.env as OPENROUTER_API_KEY.
chmod 600 ~/.hermes/.env

# Glow: verify presence without printing the value.
python - <<'PY'
from pathlib import Path
p = Path.home() / '.hermes' / '.env'
print('OPENROUTER_API_KEY:', 'present' if any(line.startswith('OPENROUTER_API_KEY=') and line.split('=', 1)[1].strip() for line in (p.read_text().splitlines() if p.exists() else [])) else 'missing')
PY

# Glow: one-off smoke test, no default change, no gateway restart.
hermes chat -Q --provider openrouter --model google/gemini-3-flash-preview -q 'Reply with exactly: openrouter-ok'
```

If that passes, OpenRouter is wired enough for deliberate model experiments. Persistent default routing is a separate Jake-approved decision.
