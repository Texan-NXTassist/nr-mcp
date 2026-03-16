"""Node-RED HTTP client with Basic Auth and optimistic locking."""

import os
import httpx


class NRError(Exception):
    """Base Node-RED error."""
    pass

class NRAuthError(NRError):
    """401/403 — bad credentials."""
    pass

class NRConflictError(NRError):
    """409 — rev mismatch, flow changed outside MCP."""
    pass

class NRNotFoundError(NRError):
    """Node, flow, or context key not found."""
    pass


class NRClient:
    """Async HTTP client for Node-RED Admin API v2."""

    def __init__(self):
        self.url = os.environ.get("NR_URL", "http://192.168.1.31:1880")
        user = os.environ.get("NR_USER", "")
        password = os.environ.get("NR_PASS", "")
        self.auth = httpx.BasicAuth(user, password)
        self._client = httpx.AsyncClient(
            base_url=self.url,
            auth=self.auth,
            timeout=30.0,
        )

    async def get_flows(self) -> tuple[list[dict], str]:
        """GET /flows — returns (flows_list, rev)."""
        r = await self._client.get("/flows", headers={"Node-RED-API-Version": "v2"})
        self._check_response(r)
        data = r.json()
        rev = data.get("rev", "")
        flows = data.get("flows", [])
        return flows, rev

    async def post_flows(self, flows: list[dict], rev: str) -> str:
        """POST /flows — full deploy with optimistic locking. Returns new rev."""
        headers = {
            "Node-RED-API-Version": "v2",
            "Node-RED-Deployment-Type": "full",
            "Content-Type": "application/json",
        }
        body = {"rev": rev, "flows": flows}
        r = await self._client.post("/flows", json=body, headers=headers)
        if r.status_code == 409:
            raise NRConflictError("Flow modified by another client (rev mismatch). Retry with fresh GET.")
        self._check_response(r)
        data = r.json()
        return data.get("rev", "")

    async def get_context(self, flow_id: str, key: str | None = None) -> dict:
        """GET /flow/:id/context[/:key] — read flow context."""
        path = f"/flow/{flow_id}/context"
        if key:
            path += f"/{key}"
        r = await self._client.get(path)
        self._check_response(r)
        return r.json()

    def _check_response(self, r: httpx.Response):
        if r.status_code in (401, 403):
            raise NRAuthError(f"Authentication failed ({r.status_code}). Check NR_USER, NR_PASS, NR_URL.")
        if r.status_code == 404:
            raise NRNotFoundError(f"Not found: {r.url}")
        if r.status_code >= 400:
            raise NRError(f"Node-RED API error {r.status_code}: {r.text[:200]}")

    async def close(self):
        await self._client.aclose()
