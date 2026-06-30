"""Gecko comprehends Surfpool.

Surfpool (https://surfpool.run, by Txtx, Apache-2.0) is a drop-in
`solana-test-validator` replacement. It has NO OpenAPI: its surface lives in
docs + Rust source (the `surfnet_*` cheatcode JSON-RPC family). This example is
the docs->draft-OpenAPI on-ramp — we authored `spec/surfpool_openapi.json` from
those sources, then let the unmodified Gecko engine comprehend it.

These tests prove the comprehension end-to-end, engine-only, $0, offline (no
network, no anthropic): intent -> the right `surfnet_*` method, a recorded call
that comes back well-formed, and the first-call-correct guard that catches a
missing required param instead of firing a malformed JSON-RPC request.

Run: uv run pytest examples/surfpool/ -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gecko import AgentApiClient, public_session
from gecko.caller import CallError

SPEC = Path(__file__).parent / "spec" / "surfpool_openapi.json"


def _client() -> AgentApiClient:
    # Local validator = no auth; the public (no-auth) session adapter.
    return AgentApiClient(str(SPEC), session=public_session())


def test_full_surface_comprehended() -> None:
    client = _client()
    names = {t["name"] for t in client.list_tools()}
    # The nine cheatcodes + five standard reads/faucet we modeled.
    assert "surfnet_setAccount" in names
    assert "surfnet_setTokenAccount" in names
    assert "surfnet_setSupply" in names
    assert "surfnet_timeTravel" in names
    assert "requestAirdrop" in names
    assert len(names) == 14


def test_search_set_account_balance_finds_set_account() -> None:
    client = _client()
    hits = [h["name"] for h in client.search("set an account's balance")]
    assert hits, "expected a discovery hit"
    assert hits[0] == "surfnet_setAccount"


def test_search_airdrop_finds_faucet_method() -> None:
    client = _client()
    hits = [h["name"] for h in client.search("airdrop SOL to a wallet")]
    assert "requestAirdrop" in hits


def test_search_time_travel_finds_cheatcode() -> None:
    client = _client()
    hits = [h["name"] for h in client.search("jump the clock to a future slot")]
    assert "surfnet_timeTravel" in hits


def test_recorded_set_account_call_is_well_formed() -> None:
    client = _client()
    result = client.call(
        "surfnet_setAccount",
        {
            "body": {
                "pubkey": "So11111111111111111111111111111111111111112",
                "update": {"lamports": 1000000000},
            }
        },
        mode="recorded",
    )
    assert result["status"] == 200
    assert result["method"] == "POST"
    # RpcResponse<()> envelope synthesized from the response schema.
    assert isinstance(result["data"], dict)
    assert "context" in result["data"]


def test_recorded_airdrop_call_returns_a_signature() -> None:
    client = _client()
    result = client.call(
        "requestAirdrop",
        {
            "body": {
                "pubkey": "So11111111111111111111111111111111111111112",
                "lamports": 1000000000,
            }
        },
        mode="recorded",
    )
    assert result["status"] == 200
    # The recorded result is the (example) base-58 funding signature string.
    assert isinstance(result["data"], str)
    assert result["data"]


def test_missing_required_param_is_caught_not_fired() -> None:
    client = _client()
    # Drop the required `pubkey` from surfnet_setAccount's params: the caller must
    # catch the malformed JSON-RPC call instead of firing it at the validator.
    with pytest.raises(CallError) as exc:
        client.call(
            "surfnet_setAccount",
            {"body": {"update": {"lamports": 1000000000}}},
            mode="recorded",
        )
    assert "pubkey" in str(exc.value)


def test_local_validator_needs_no_auth() -> None:
    # No surfaced tool should be auth-gated — a local validator has no paywall.
    client = _client()
    assert all(not t.get("requires_auth") for t in client.list_tools())
