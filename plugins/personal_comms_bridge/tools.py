"""Read-only tool client for Jake's localhost personal-comms-bridge service."""

from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from tools.registry import tool_error, tool_result

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8765"
BRIDGE_URL_ENV = "PERSONAL_COMMS_BRIDGE_URL"
BRIDGE_TIMEOUT_ENV = "PERSONAL_COMMS_BRIDGE_TIMEOUT"
_MAX_LIMIT = 100
_CONNECTOR_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CommsBridgeError(Exception):
    """Base error for bridge client failures."""


class CommsBridgeConfigError(CommsBridgeError):
    """The requested client configuration is unsafe or invalid."""


class CommsBridgeHTTPError(CommsBridgeError):
    """The bridge returned an HTTP error."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class BridgeClient:
    base_url: str = DEFAULT_BRIDGE_URL
    timeout: float = 3.0

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = _join_url(self.base_url, path, params=params)
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "Hermes personal-comms-bridge/0.1"})
        try:
            with urlopen(req, timeout=self.timeout) as response:  # nosec B310 - localhost URL validated below
                body = response.read().decode("utf-8")
                if not body:
                    return None
                return json.loads(body)
        except HTTPError as exc:
            detail = _parse_error_body(exc)
            raise CommsBridgeHTTPError(
                f"personal-comms-bridge returned HTTP {exc.code}",
                status_code=exc.code,
                detail=detail,
            ) from exc
        except URLError as exc:
            raise CommsBridgeHTTPError(f"personal-comms-bridge is unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise CommsBridgeHTTPError("personal-comms-bridge request timed out") from exc
        except json.JSONDecodeError as exc:
            raise CommsBridgeHTTPError("personal-comms-bridge returned non-JSON response") from exc


def check_personal_comms_bridge_available() -> bool:
    """Tool availability gate: expose the client when its URL is safely local.

    Do not require a live `/health` response here: the health action itself is
    how the agent/user diagnoses whether the sidecar is running.
    """
    try:
        _client_from_env(timeout_default=0.5)
        return True
    except Exception:
        return False


PERSONAL_COMMS_BRIDGE_SCHEMA = {
    "name": "personal_comms_bridge",
    "description": (
        "Read-only client for Jake's private localhost personal-comms-bridge sidecar. "
        "Use it for bridge health, connector inventory/status, recent metadata/snippet previews, "
        "and attention radar. It never sends replies, deletes, archives, marks read/unread, or opens threads."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "health",
                    "connectors",
                    "connector_status",
                    "recent",
                    "attention",
                    "connector_attention",
                ],
                "description": "Safe read-only bridge operation to perform.",
            },
            "connector": {
                "type": "string",
                "description": "Connector name for connector-specific actions, e.g. gmail, google_messages, facebook_messenger.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_LIMIT,
                "description": "Maximum preview candidates to return for recent/attention actions.",
            },
            "base_url": {
                "type": "string",
                "description": (
                    "Optional bridge URL override. Must resolve to localhost/loopback. "
                    f"Defaults to {BRIDGE_URL_ENV} or {DEFAULT_BRIDGE_URL}."
                ),
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def handle_personal_comms_bridge(args: dict, **kw) -> str:
    """Dispatch a safe read-only bridge action and return JSON."""
    try:
        action = str(args.get("action") or "health").strip().lower()
        client = _client_from_args(args)

        if action == "health":
            return tool_result({"success": True, "action": action, "bridge": client.get("/health")})

        if action == "connectors":
            return tool_result({"success": True, "action": action, "result": client.get("/connectors")})

        if action == "connector_status":
            connector = _required_connector(args)
            return tool_result({
                "success": True,
                "action": action,
                "connector": connector,
                "result": client.get(f"/connectors/{connector}/status"),
            })

        if action == "recent":
            connector = _required_connector(args)
            limit = _coerce_limit(args.get("limit"))
            return tool_result({
                "success": True,
                "action": action,
                "connector": connector,
                "limit": limit,
                "result": client.get(f"/connectors/{connector}/recent", {"limit": limit}),
            })

        if action == "attention":
            limit = _coerce_limit(args.get("limit"))
            return tool_result({
                "success": True,
                "action": action,
                "limit": limit,
                "result": client.get("/attention/recent", {"limit": limit}),
            })

        if action == "connector_attention":
            connector = _required_connector(args)
            limit = _coerce_limit(args.get("limit"))
            return tool_result({
                "success": True,
                "action": action,
                "connector": connector,
                "limit": limit,
                "result": client.get(f"/connectors/{connector}/attention", {"limit": limit}),
            })

        return tool_error(f"Unsupported personal_comms_bridge action: {action}", success=False)
    except CommsBridgeHTTPError as exc:
        return tool_error(str(exc), success=False, status_code=exc.status_code, detail=exc.detail)
    except CommsBridgeConfigError as exc:
        return tool_error(str(exc), success=False)
    except Exception as exc:  # defensive: tool calls should fail closed, not crash the agent loop
        return tool_error(f"personal_comms_bridge failed: {type(exc).__name__}: {exc}", success=False)


def _client_from_args(args: dict[str, Any]) -> BridgeClient:
    base_url = str(args.get("base_url") or os.getenv(BRIDGE_URL_ENV) or DEFAULT_BRIDGE_URL).strip()
    timeout = _timeout_from_env()
    _validate_loopback_url(base_url)
    return BridgeClient(base_url=base_url.rstrip("/"), timeout=timeout)


def _client_from_env(*, timeout_default: float) -> BridgeClient:
    base_url = str(os.getenv(BRIDGE_URL_ENV) or DEFAULT_BRIDGE_URL).strip()
    timeout = _timeout_from_env(default=timeout_default)
    _validate_loopback_url(base_url)
    return BridgeClient(base_url=base_url.rstrip("/"), timeout=timeout)


def _timeout_from_env(default: float = 3.0) -> float:
    raw = os.getenv(BRIDGE_TIMEOUT_ENV)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.1, min(30.0, value))


def _validate_loopback_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise CommsBridgeConfigError("personal-comms-bridge base_url must use http or https")
    if parsed.username or parsed.password:
        raise CommsBridgeConfigError("personal-comms-bridge base_url must not include credentials")
    host = parsed.hostname
    if not host:
        raise CommsBridgeConfigError("personal-comms-bridge base_url must include a host")
    if host in {"localhost", "127.0.0.1", "::1"}:
        return
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CommsBridgeConfigError(f"personal-comms-bridge base_url host is not resolvable: {host}") from exc
    if not addresses or not all(_is_loopback_address(info[4][0]) for info in addresses):
        raise CommsBridgeConfigError("personal-comms-bridge base_url must resolve only to localhost/loopback")


def _is_loopback_address(address: str) -> bool:
    return address == "::1" or address.startswith("127.")


def _join_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    query = f"?{urlencode(params)}" if params else ""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}{query}"


def _required_connector(args: dict[str, Any]) -> str:
    connector = str(args.get("connector") or "").strip()
    if not connector:
        raise CommsBridgeConfigError("connector is required for this action")
    if not _CONNECTOR_RE.match(connector):
        raise CommsBridgeConfigError("connector must contain only letters, digits, underscores, or hyphens")
    return connector


def _coerce_limit(raw: Any, *, default: int = 25) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(1, min(_MAX_LIMIT, value))


def _parse_error_body(exc: HTTPError) -> Any:
    try:
        body = exc.read().decode("utf-8")
        if not body:
            return None
        return json.loads(body)
    except Exception:
        return None
