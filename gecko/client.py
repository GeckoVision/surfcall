"""AgentApiClient — the one object that makes an API agent-usable.

Ties the layers together: ingest -> catalog (find) -> tools (comprehend) ->
caller (correct request) -> access (auth) -> response. Two modes:
  - "recorded": synthesize the response from the spec (no network, no spend) — for demos/CI.
  - "live": actually call the upstream API with the session's auth.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from .access import AuthSession, stub_session
from .caller import CallError, PreparedRequest, build_request, execute
from .catalog import Catalog
from .ingest import extract_operations, load_spec
from .sample import example_from_schema
from .tools import build_tools, to_tool


class AgentApiClient:
    def __init__(
        self,
        spec: str | dict,
        base_url: str | None = None,
        session: AuthSession | None = None,
    ):
        """Make an API agent-usable from its OpenAPI spec.

        Live mode targets ``servers[0].url`` from the spec unless an explicit
        ``base_url`` is given. This is a money-API footgun: if the spec lists a
        production server first, a live call hits production — pass the sandbox
        server's URL explicitly for live tests. An explicit ``base_url`` also pins
        auth injection to that one host (see ``self._auth_allowed_hosts``).
        """
        self.spec = load_spec(spec) if isinstance(spec, str) else spec
        # The raw spec servers list, exposed so callers can choose a non-default
        # server explicitly (e.g. a sandbox) instead of silently using servers[0].
        self.servers = self.spec.get("servers") or []
        servers = self.servers or [{}]
        self.base_url = base_url or servers[0].get("url", "")
        # Hosts we'll let the session's auth headers reach. Explicit base_url => pin to
        # that one host (the protected mode). Otherwise trust the spec's own server
        # hosts. See the RESIDUAL note in caller.build_request.
        if base_url is not None:
            pinned = urlsplit(base_url).hostname
            self._auth_allowed_hosts: set[str] = {pinned.lower()} if pinned else set()
        else:
            self._auth_allowed_hosts = {
                host.lower()
                for s in servers
                if isinstance(s, dict) and (host := urlsplit(s.get("url", "")).hostname)
            }
        self.operations = extract_operations(self.spec)
        self.catalog = Catalog(self.operations)
        self.tools = build_tools(self.operations)
        self._tool_by_name = {t["name"]: t for t in self.tools}
        self._op_by_name = {to_tool(o)["name"]: o for o in self.operations}
        self.session = session or stub_session()
        # An empty auth-header dict means the session can't satisfy auth-gated ops,
        # so we hide them from the agent (it would only mis-call them). A session
        # WITH auth (e.g. TxODDS) surfaces everything, unchanged.
        self._session_has_auth = bool(self.session.auth_headers())
        self._usable_tool_names = {
            t["name"]
            for t in self.tools
            if self._session_has_auth or not t.get("requires_auth")
        }

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for e in self.catalog.search(query, limit + 20):
            if e.tool_name not in self._usable_tool_names:
                continue
            out.append(
                {
                    "name": e.tool_name,
                    "summary": e.operation.summary,
                    "path": e.operation.path,
                    "method": e.operation.method,
                }
            )
            if len(out) >= limit:
                break
        return out

    def list_tools(self) -> list[dict[str, Any]]:
        return [t for t in self.tools if t["name"] in self._usable_tool_names]

    def prepare(self, tool_name: str, args: dict[str, Any]) -> PreparedRequest:
        tool = self._tool_by_name[tool_name]
        if tool.get("requires_auth") and not self._session_has_auth:
            raise CallError(
                f"tool '{tool_name}' requires authentication the current session "
                f"cannot provide (schemes: {tool.get('auth_schemes')})"
            )
        return build_request(
            tool,
            args,
            self.base_url,
            self.session.auth_headers(),
            allowed_auth_hosts=self._auth_allowed_hosts,
        )

    def call(
        self, tool_name: str, args: dict[str, Any], mode: str = "recorded"
    ) -> dict[str, Any]:
        req = self.prepare(tool_name, args)
        if mode == "live":
            status, body = execute(req)
            return {
                "status": status,
                "request": req.url,
                "method": req.method,
                "data": body,
                "mode": "live",
            }
        schema = self._success_schema(self._op_by_name[tool_name])
        return {
            "status": 200,
            "request": req.url,
            "method": req.method,
            "data": example_from_schema(schema),
            "mode": "recorded",
        }

    @staticmethod
    def _success_schema(op) -> dict[str, Any]:
        for code in ("200", "201", "default"):
            r = op.responses.get(code)
            if not isinstance(r, dict):
                continue
            content = r.get("content", {}) or {}
            media = content.get("application/json") or next(
                iter(content.values()), None
            )
            if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                return media["schema"]
        return {}
