"""HTTP client for the Dockmaster server API (server.js)."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import REQUEST_TIMEOUT


class DockmasterError(Exception):
    """The Dockmaster server could not be reached or returned an error."""


class DockmasterClient:
    """Thin wrapper around the Dockmaster REST endpoints."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(method, url, **kwargs) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status >= 400:
                        message = data.get("error") if isinstance(data, dict) else None
                        raise DockmasterError(message or f"HTTP {resp.status}")
                    return data
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise DockmasterError(str(err) or type(err).__name__) from err

    async def get_health(self) -> dict[str, Any]:
        """NAS SSH connectivity: {"connected": bool, "host": str}."""
        return await self._request("GET", "/api/health")

    async def get_apps(self) -> list[dict[str, Any]]:
        """All compose apps on every host, with per-service state."""
        return (await self._request("GET", "/api/apps"))["apps"]

    async def get_nas_stats(self) -> dict[str, Any]:
        """NAS RAM, uptime, CPU %, temperature."""
        return await self._request("GET", "/api/system")

    async def get_pi_stats(self) -> dict[str, Any]:
        """Same stats for the device running Dockmaster."""
        return await self._request("GET", "/api/host")

    async def get_docker_stats(self) -> dict[str, Any]:
        """Aggregate container CPU and memory on the NAS."""
        return await self._request("GET", "/api/stats")

    async def app_action(self, host: str, app: str, action: str) -> None:
        """action is 'start' or 'stop' (docker compose up -d / stop)."""
        await self._request(
            "POST", f"/api/apps/{quote(app)}/{action}", params={"host": host}
        )

    async def service_action(self, host: str, app: str, service: str, action: str) -> None:
        await self._request(
            "POST",
            f"/api/apps/{quote(app)}/services/{quote(service)}/{action}",
            params={"host": host},
        )

    async def all_apps_action(self, action: str) -> None:
        """action is 'start' or 'stop' across every host."""
        await self._request("POST", f"/api/{action}-all")
