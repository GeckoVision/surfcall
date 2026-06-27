"""AgentApiClient — the one object that makes an API agent-usable.

Ties the layers together: ingest -> catalog (find) -> tools (comprehend) ->
caller (correct request) -> access (auth) -> response. Two modes:
  - "recorded": synthesize the response from the spec (no network, no spend) — for demos/CI.
  - "live": actually call the upstream API with the session's auth.
"""

from __future__ import annotations

from typing import Any

from .access import Session, stub_session
from .caller import PreparedRequest, build_request, execute
from .catalog import Catalog
from .ingest import extract_operations, load_spec
from .sample import example_from_schema
from .tools import build_tools, to_tool


class AgentApiClient:
    def __init__(self, spec: str | dict, base_url: str | None = None, session: Session | None = None):
        self.spec = load_spec(spec) if isinstance(spec, str) else spec
        servers = self.spec.get("servers") or [{}]
        self.base_url = base_url or servers[0].get("url", "")
        self.operations = extract_operations(self.spec)
        self.catalog = Catalog(self.operations)
        self.tools = build_tools(self.operations)
        self._tool_by_name = {t["name"]: t for t in self.tools}
        self._op_by_name = {to_tool(o)["name"]: o for o in self.operations}
        self.session = session or stub_session()

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {"name": e.tool_name, "summary": e.operation.summary, "path": e.operation.path,
             "method": e.operation.method}
            for e in self.catalog.search(query, limit)
        ]

    def list_tools(self) -> list[dict[str, Any]]:
        return self.tools

    def prepare(self, tool_name: str, args: dict[str, Any]) -> PreparedRequest:
        tool = self._tool_by_name[tool_name]
        return build_request(tool, args, self.base_url, self.session.auth_headers())

    def call(self, tool_name: str, args: dict[str, Any], mode: str = "recorded") -> dict[str, Any]:
        req = self.prepare(tool_name, args)
        if mode == "live":
            status, body = execute(req)
            return {"status": status, "request": req.url, "method": req.method, "data": body, "mode": "live"}
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
            media = content.get("application/json") or next(iter(content.values()), None)
            if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                return media["schema"]
        return {}
