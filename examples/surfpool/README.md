# Gecko comprehends Surfpool

**Surfpool forks the chain; Gecko comprehends Surfpool's RPC so an agent drives it correctly.**

[Surfpool](https://surfpool.run) (by [Txtx](https://github.com/solana-foundation/surfpool), Apache-2.0)
is a drop-in `solana-test-validator` replacement: it forks mainnet locally,
serves Solana JSON-RPC on `http://localhost:8899` (dashboard on `:18488`), and
adds a **`surfnet_*` cheatcode** family for deterministic state manipulation —
set an account's balance, mint into a token account, override supply, time-travel
the clock, clone a program. Powerful surface, but an agent can't *use* it without
knowing the exact method names and param shapes.

This example points Gecko at that surface and turns it into question-shaped,
first-call-correct agent tools — so an agent can find the right `surfnet_*` call
and shape it correctly the first time.

## The honest part: this is the docs→draft-OpenAPI on-ramp

Surfpool ships **no OpenAPI**. Its surface lives in human-shaped docs and Rust
source — exactly the "Nth painful API" Gecko exists for. So the source here is
**docs, not a spec**:

- Method names + params were sourced from the cheatcodes RPC trait in
  [`crates/core/src/rpc/surfnet_cheatcodes.rs`](https://github.com/solana-foundation/surfpool/blob/main/crates/core/src/rpc/surfnet_cheatcodes.rs)
  and the typed params in
  [`crates/types/src/types.rs`](https://github.com/solana-foundation/surfpool/blob/main/crates/types/src/types.rs)
  + [`crates/core/src/types.rs`](https://github.com/solana-foundation/surfpool/blob/main/crates/core/src/types.rs),
  cross-checked against [`docs.surfpool.run/rpc/cheatcodes`](https://docs.surfpool.run/rpc/cheatcodes).
- We authored those into [`spec/surfpool_openapi.json`](spec/surfpool_openapi.json) (OpenAPI 3.1).
- The **unmodified Gecko engine** comprehends that spec — no Surfpool-specific code in `gecko/`.

Nothing here is invented: every operation maps to a real `surfnet_*` method or a
standard Solana RPC read. Where the source left a param shape ambiguous it's
noted in the spec (e.g. `TimeTravelConfig` is an untagged enum; field names are
the serde camelCase form of the Rust structs).

## The JSON-RPC ↔ OpenAPI mismatch (handled, not hidden)

Surfpool is **JSON-RPC, not REST**. Every call is really *one* `POST /` whose body
is the envelope:

```json
{ "jsonrpc": "2.0", "id": 1, "method": "surfnet_setAccount", "params": [pubkey, update] }
```

OpenAPI requires a unique `(path, method)` per operation, so we model each RPC
method as **its own** question-shaped operation:

- `operationId` = the exact JSON-RPC method (`surfnet_setAccount`),
- `path` = a virtual `/{method}` route (so the catalog has 14 distinct operations),
- `requestBody` = that method's params, by name, with genuinely-required params
  marked `required`,
- the true wire target is carried on each op as `x-jsonrpc-endpoint: "/"` and
  `x-jsonrpc-method`.

**Recorded vs live:** this is a comprehension / **recorded** demo — each method is
surfaced directly so the agent can *discover and shape* the call. A **live** caller
wraps the `requestBody` under `params` in the JSON-RPC envelope and POSTs to
`x-jsonrpc-endpoint` (`/`). Local validator ⇒ **no auth**. (A thin JSON-RPC
transport adapter at `Session`/caller level is the natural next step to make the
live path one-line; the comprehension above is what's proven here.)

## What's comprehended

| Tag | Operations |
|---|---|
| `cheatcodes` | `surfnet_setAccount`, `surfnet_setTokenAccount`, `surfnet_setSupply`, `surfnet_timeTravel`, `surfnet_pauseClock`, `surfnet_resumeClock`, `surfnet_cloneProgramAccount`, `surfnet_setProgramAuthority`, `surfnet_resetAccount` |
| `standard-rpc` | `requestAirdrop`, `getBalance`, `getSlot`, `getAccountInfo`, `getSupply` |

(The standard reads give discovery some range — an agent asking "what's this
wallet's balance" shouldn't land on a cheatcode.)

## Run it ($0, offline, no API key)

```bash
uv run pytest examples/surfpool/ -q
```

The tests assert the comprehension directly:

- `client.search("set an account's balance")` → **`surfnet_setAccount`**
- `client.search("airdrop SOL to a wallet")` → **`requestAirdrop`** (the faucet)
- `client.search("jump the clock to a future slot")` → **`surfnet_timeTravel`**
- a recorded `surfnet_setAccount` call → `200` + a well-formed `RpcResponse<()>`
- dropping the required `pubkey` → **`gecko.caller.CallError`** (the malformed call
  is *caught*, not fired at the validator)

```python
from gecko import AgentApiClient, public_session

client = AgentApiClient("examples/surfpool/spec/surfpool_openapi.json",
                        session=public_session())  # local validator = no auth
hit = client.search("set an account's balance")[0]          # -> surfnet_setAccount
client.call(hit["name"],
            {"body": {"pubkey": "<base58>", "update": {"lamports": 1_000_000_000}}},
            mode="recorded")                                 # "live" once the JSON-RPC adapter lands
```

## What's real today vs. later

- **Live today:** the comprehension above — docs/source → a spec → first-call-correct
  agent tools an agent can search and shape, recorded and $0-falsifiable offline.
- **V2 / cloud (not claimed here):** continuous re-ingest as Surfpool's surface
  drifts, a hosted MCP endpoint, and the JSON-RPC transport adapter that closes the
  live loop end-to-end against a running `:8899`.

No metrics are claimed — this is a comprehension showcase, not a benchmark.

## Credit

Surfpool is built by [Txtx](https://txtx.sh) and the Solana Foundation, Apache-2.0:
<https://github.com/solana-foundation/surfpool>. This example only *reads* Surfpool's
public surface to make it agent-usable; Gecko stays control-plane only and stores
no Surfpool response data.
