# personal-comms-bridge Hermes plugin

Thin local Hermes integration for Jake's private `personal-comms-bridge` sidecar.

## Integration shape

This is a bundled/local plugin, not a core `tools/` module and not connector scraping code. Hermes only gets one thin read-only HTTP client tool:

- `personal_comms_bridge(action="health")` -> `GET /health`
- `personal_comms_bridge(action="connectors")` -> `GET /connectors`
- `personal_comms_bridge(action="connector_status", connector="gmail")` -> `GET /connectors/gmail/status`
- `personal_comms_bridge(action="recent", connector="google_messages", limit=10)` -> `GET /connectors/google_messages/recent?limit=10`
- `personal_comms_bridge(action="attention", limit=10)` -> `GET /attention/recent?limit=10`
- `personal_comms_bridge(action="connector_attention", connector="gmail", limit=10)` -> `GET /connectors/gmail/attention?limit=10`

The Gmail, Google Messages, and Facebook Messenger implementation details stay in `/home/methodician/projects/personal-comms-bridge`. This plugin only calls the bridge API.

## Safety posture

- Read-only operations only.
- No send/reply/delete/archive/mark-read/mark-unread/thread-opening paths.
- Routine calls return bridge-provided metadata/snippets/candidate IDs only.
- `base_url` defaults to `http://127.0.0.1:8765` and must be localhost/loopback. Non-loopback hosts are rejected.
- No live Hermes gateway restart is needed to run tests or a CLI smoke check.

## Activation

If this plugin is not already loaded by the checkout, enable it in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - personal-comms-bridge
```

Then start a fresh CLI session with the toolset enabled:

```bash
hermes chat --toolsets personal_comms_bridge -q "Check the personal comms bridge health"
```

Optional environment variables:

```bash
export PERSONAL_COMMS_BRIDGE_URL=http://127.0.0.1:8765
export PERSONAL_COMMS_BRIDGE_TIMEOUT=10
```

Do not restart the live gateway unless Jake explicitly approves. CLI sessions and tests can exercise the integration without touching gateway state.

## Direct developer smoke without gateway

From `/home/methodician/projects/hermes-agent`:

```bash
python - <<'PY'
from plugins.personal_comms_bridge.tools import handle_personal_comms_bridge
print(handle_personal_comms_bridge({"action": "health"}))
PY
```

If the bridge is not running, the tool fails closed with a JSON error instead of trying to launch or mutate anything.
