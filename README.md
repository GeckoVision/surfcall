# surfcall (working name)

**Make any API agent-usable without integration code.**

Point an agent at an API — even one behind human-shaped docs and a paywall — and it can find the right call, make it correctly the first time, and run. Today a builder reads the docs, writes a client, and still can't tell if the agent is calling it right. This removes that step.

## V1 scope — the comprehension layer (one API: TxODDS)
1. **Ingest** the API's *surface* (OpenAPI/docs) — endpoints, params, schemas. Never the response data.
2. **Comprehend** — turn it into question-shaped, first-call-correct agent tools.
3. **Catalog** — a structured capability list (intent → endpoint). No vectors at this scale.
4. **Access** — drive the on-chain subscription handshake; the agent then calls the API *directly* for data.
5. **Expose** — as an MCP server / agent-skill.
6. **Validate** — replay calls, confirm first-call-correct, log outcomes (seeds the moat).

**Data governance:** we store the API surface + generated tool defs + correctness metadata. We never store responses, user data, or secrets.

**Not vectorized in V1** (deferred to multi-API V2). **Not** a payment rail (that's x402/Metera) or a marketplace (frames.ag) — this is the *comprehension* layer.

## What's built (V1, against the real TxODDS spec)
`ingest` · `catalog` (find) · `tools` (comprehend, auth hidden) · `caller` (correct request) · `access` (two-token session) · `sample` (recorded responses) · `client` (recorded/live) · `mcp_server` (agent surface) · `validator` (correctness + flywheel log) · `demo`. **31 tests passing.**

## Dev
```bash
uv sync
uv run pytest                      # 31 passing
uv run python -m surfcall.demo     # E2E: goal -> discover -> correct call -> data ($0, recorded)
```

## Going live
Recorded mode needs no subscription. For live World Cup data, do the one-time on-chain subscribe — see [scripts/SUBSCRIBE.md](scripts/SUBSCRIBE.md) — then pass a real `Session` to `AgentApiClient(..., session=...)` and call with `mode="live"`. Same code path.

> Fresh repo, zero dependency on the old Builder-Bootstrap product. Rename + `git init` on brand pick.
