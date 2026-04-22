"""Node-RED HTTP client with auth and optimistic locking."""

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
    """Async HTTP client for Node-RED Admin API v2.

    Authentication methods (checked in order):
    1. Bearer token: set NR_TOKEN env var
    2. Basic Auth: set NR_USER + NR_PASS env vars
    3. No auth: if none of the above are set (for unsecured instances)

    Environment variables:
        NR_URL:        Node-RED base URL (default: http://localhost:1880)
        NR_TOKEN:      Bearer token for token-based auth
        NR_USER:       Username for Basic Auth
        NR_PASS:       Password for Basic Auth
        NR_VERIFY_SSL: Set to 0/false/no to disable TLS certificate
                       verification (useful for self-signed certs).
                       Defaults to 1 (verification enabled).
    """

    def __init__(self):
        self.url = os.environ.get("NR_URL", "http://localhost:1880")
        token = os.environ.get("NR_TOKEN", "")
        user = os.environ.get("NR_USER", "")
        password = os.environ.get("NR_PASS", "")

        # Determine auth method
        auth = None
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif user:
            auth = httpx.BasicAuth(user, password)

        verify_ssl = os.environ.get("NR_VERIFY_SSL", "1").strip().lower() not in ("0", "false", "no")
        self._client = httpx.AsyncClient(
            base_url=self.url,
            auth=auth,
            headers=headers,
            timeout=30.0,
            verify=verify_ssl,
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

    async def get_context(self, flow_id: str) -> dict:
        """GET /context/flow/:id — read flow context. Returns raw API response."""
        path = f"/context/flow/{flow_id}"
        r = await self._client.get(path)
        self._check_response(r)
        return r.json()

    async def inject(self, node_id: str) -> bool:
        """POST /inject/:id — trigger an inject node."""
        resp = await self._client.post(f"/inject/{node_id}")
        if resp.status_code == 200:
            return True
        elif resp.status_code == 404:
            raise NRNotFoundError(f"Inject node '{node_id}' not found")
        else:
            raise NRError(f"Inject failed: {resp.status_code} {resp.text}")

    async def get_nodes(self) -> list[dict]:
        """GET /nodes — list all installed node modules and types."""
        resp = await self._client.get(
            "/nodes",
            headers={"Accept": "application/json", "Node-RED-API-Version": "v2"},
        )
        self._check_response(resp)
        return resp.json()

    async def install_module(self, module_name: str) -> dict:
        """POST /nodes — install a new npm module."""
        resp = await self._client.post(
            "/nodes",
            json={"module": module_name},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=120.0,
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            raise NRError(f"Module '{module_name}' not found or invalid")
        elif resp.status_code == 409:
            raise NRError(f"Module '{module_name}' already installed")
        else:
            raise NRError(f"Install failed: {resp.status_code} {resp.text}")

    def _check_response(self, r: httpx.Response):
        if r.status_code in (401, 403):
            raise NRAuthError(f"Authentication failed ({r.status_code}). Check NR_TOKEN or NR_USER/NR_PASS and NR_URL.")
        if r.status_code == 404:
            raise NRNotFoundError(f"Not found: {r.url}")
        if r.status_code >= 400:
            raise NRError(f"Node-RED API error {r.status_code}: {r.text[:200]}")

    async def close(self):
        await self._client.aclose()
