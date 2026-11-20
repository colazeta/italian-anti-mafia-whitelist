from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from white_list_archive.mcp_public.store import SnapshotStore

STORE = SnapshotStore()

INSTRUCTIONS = """
Whitelist Explorer is a read-only research interface to the reviewed public
snapshot of the Open Italian Anti-Mafia White List Archive.

Treat every registry result as a source-backed observation, not as a nationally
deduplicated legal entity and not as certification of current administrative
status. Preserve provenance. Never infer administrative removal from
disappearance between editions. Never treat a nominal expiry date as automatic
loss of legal effect. Distinguish a discovered/mapped Prefecture source from a
Prefecture whose row-level data are present in the selected public snapshot.
""".strip()

mcp = MCPServer(
    "Whitelist Explorer",
    instructions=INSTRUCTIONS,
    website_url="https://colazeta.github.io/italian-anti-mafia-whitelist/",
)


@mcp.tool()
def search_registry(
    query: str = "",
    authority: str | None = None,
    status: str | None = None,
    register: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search reviewed public White List observations.

    Use identifiers when available. authority accepts a Prefecture key or name.
    Results are source observations, not deduplicated companies.
    """
    return STORE.search_registry(
        query,
        authority=authority,
        status=status,
        register=register,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_observation(record_locator: str) -> dict[str, Any]:
    """Return one exact public observation by its stable record locator."""
    return STORE.get_observation(record_locator)


@mcp.tool()
def get_prefecture(authority: str) -> dict[str, Any]:
    """Return public coverage metadata and registry aggregates for one Prefecture."""
    return STORE.get_prefecture(authority)


@mcp.tool()
def compare_prefectures(
    authorities: list[str],
    status: str | None = None,
) -> dict[str, Any]:
    """Compare up to 20 Prefectures using explicit source-observation denominators."""
    return STORE.compare_prefectures(authorities, status=status)


@mcp.tool()
def date_distribution(
    kind: str,
    authority: str | None = None,
    status: str | None = None,
    bucket: str = "month",
) -> dict[str, Any]:
    """Build a date distribution from the selected public snapshot.

    kind is one of application, expiry, reference or listing.
    bucket is year, month or day. Unknown or unusable dates are reported explicitly.
    """
    return STORE.date_distribution(
        kind,
        authority=authority,
        status=status,
        bucket=bucket,
    )


@mcp.tool()
def get_history(
    authority: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return aggregate edition history and observational comparisons."""
    return STORE.get_history(authority=authority, limit=limit)


@mcp.tool()
def get_robot_directory(authority: str | None = None) -> dict[str, Any]:
    """Return reviewed Prefecture robot configuration.

    This is configuration and source-mapping metadata, not live execution health.
    """
    return STORE.get_robot_directory(authority=authority)


@mcp.tool()
def get_dataset_metadata() -> dict[str, Any]:
    """Return selected-release identity, denominators and public archive metadata."""
    return STORE.get_dataset_metadata()


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "whitelist-explorer-mcp",
            "version": "0.2.0",
        }
    )


def main() -> None:
    port = int(os.environ.get("PORT", "10000"))
    # Render terminates TLS and controls the public Host header. The service is
    # read-only and exposes public data only, so proxy-level Host control is the
    # deployment boundary for DNS-rebinding protection.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        json_response=True,
        stateless_http=True,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
