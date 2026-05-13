"""Personal comms bridge plugin.

This is intentionally a thin, local-only client for Jake's private
personal-comms-bridge sidecar. Connector scraping/OAuth/browser automation stays
outside Hermes core; this plugin only calls the bridge's safe read-only HTTP API.
"""

from __future__ import annotations

from plugins.personal_comms_bridge.tools import (
    PERSONAL_COMMS_BRIDGE_SCHEMA,
    check_personal_comms_bridge_available,
    handle_personal_comms_bridge,
)


def register(ctx) -> None:
    """Register the read-only comms bridge tool."""
    ctx.register_tool(
        name="personal_comms_bridge",
        toolset="personal_comms_bridge",
        schema=PERSONAL_COMMS_BRIDGE_SCHEMA,
        handler=handle_personal_comms_bridge,
        check_fn=check_personal_comms_bridge_available,
        emoji="📬",
    )
