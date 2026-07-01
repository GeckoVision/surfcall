"""Red-team showcase: Gecko treats an OpenAPI spec as UNTRUSTED and blocks poisoning.

Six poisoned specs (``specs/*.json``), each a real attack that slips past the common
"just turn the OpenAPI into MCP tools" pipeline because that pipeline **trusts the spec**.
For each, we assert Gecko blocks / quarantines / sanitizes it, and — where cheap — that the
naive baseline (``naive.py``) would fall for it, so the value is concrete.

Engine-only, $0, fully offline (no network, no anthropic, no secrets). Run:

    uv run pytest examples/poisoning_showcase/ -q

Attack -> defense that catches it:
  1 server_url_exfil    -> out-of-band trust anchor (auth host never from servers[])
  2 privkey_seed_leak   -> text sanitizer + quarantine (instruction stripped, no auth)
  3 apikey_echo_default -> schema sanitizer (secret default/example dropped from args)
  4 fund_transfer       -> fund-routing sanitizer + quarantine (attacker default dropped)
  5 auth_location_drift -> auth-location pin (refuse to inject secret into a loggable URL)
  6 dropped_required    -> required-guard + tools_rev integrity anchor
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gecko import corpus
from gecko.access import Session, public_session
from gecko.caller import CallError, build_request
from gecko.client import AgentApiClient, IntegrityError
from gecko.ingest import extract_operations
from gecko.sample import example_from_schema
from gecko.tools import to_tool

from . import naive

SPECS = Path(__file__).parent / "specs"


def _spec(name: str) -> dict[str, Any]:
    """Load a poisoned spec as an in-memory dict — the realistic 'untrusted blob handed
    to us by a registry / marketplace / URL fetch' provenance (no dev-vouched file path)."""
    return json.loads((SPECS / f"{name}.json").read_text())


def _first_op(spec: dict[str, Any]) -> Any:
    return extract_operations(spec)[0]


# =====================================================================================
# Attack 1 — key exfiltration via servers[].url
# A poisoned servers[] points the base host at an attacker. A naive tool derives its
# auth target from servers[] and ships the customer's secret to the attacker on call 1.
# =====================================================================================
def test_attack1_auth_never_injected_toward_poisoned_server_host() -> None:
    spec = _spec("01_server_url_exfil")
    client = AgentApiClient(
        spec, session=Session(jwt="SECRET_JWT", api_token="SECRET_TOK")
    )

    # No out-of-band provenance for a raw blob -> unverified -> fail closed, no anchor host.
    assert client.anchor.state == "unverified"
    assert client._auth_allowed_hosts == set()

    req = client.prepare("getForecast", {"city": "lima"})
    assert "Authorization" not in req.headers
    assert "X-Api-Token" not in req.headers
    assert "SECRET" not in str(req.headers)  # the token never reaches the wire


def test_attack1_live_call_degrades_to_recorded_not_exfil() -> None:
    spec = _spec("01_server_url_exfil")
    client = AgentApiClient(spec, session=Session(jwt="J", api_token="T"))
    # A live auth-expecting call on an unverified surface must not fire (it would hit the
    # attacker host un-authenticated); it degrades to recorded — no network, no leak.
    assert (
        client.call("getForecast", {"city": "lima"}, mode="live")["mode"] == "recorded"
    )


def test_attack1_auth_host_blocked_is_recorded_without_leaking_host_or_token(
    tmp_path: Path,
) -> None:
    # The corpus-visible outcome of the defense firing. Provenance scenario: a spec
    # ingested FROM a URL pins the anchor to the ingest host, but servers[0] (attacker-
    # controlled) drifts elsewhere. Injection is refused and recorded as the countable,
    # value-free ``auth_host_blocked`` — the same functions client._capture() uses.
    tool = to_tool(_first_op(_spec("01_server_url_exfil")))
    with pytest.raises(CallError) as exc:
        build_request(
            tool,
            {"city": "lima"},
            base_url="https://evil.attacker.test",  # spec's drifted servers[0]
            auth={"Authorization": "Bearer SECRET_TOKEN"},
            allowed_auth_hosts={"docs.trusted-ingest.test"},  # the out-of-band anchor
        )
    assert "refusing to inject auth" in str(exc.value)
    assert "SECRET_TOKEN" not in str(
        exc.value
    )  # message names only the host, not the secret

    error_class = corpus.error_class_for(None, exc.value)
    assert error_class == "auth_host_blocked"

    log = tmp_path / "corpus.jsonl"
    corpus.record(
        corpus.outcome_from(
            operation_id="getForecast",
            tool_invoke=tool["_invoke"],
            args={"city": "lima"},
            status=None,
            error_class=error_class,
            latency_ms=None,
            mode="live",
            auth_injected=False,
            ts=0,
            surface_id="poison-1",
            surface_rev="rev",
        ),
        log,
    )
    text = log.read_text()
    assert "auth_host_blocked" in text
    # Control-plane only: no host, no token, no arg VALUE ever lands in the corpus.
    assert "evil.attacker.test" not in text
    assert "SECRET_TOKEN" not in text
    assert "lima" not in text


def test_attack1_naive_baseline_would_exfil_to_attacker() -> None:
    spec = _spec("01_server_url_exfil")
    # Contrast: a naive tool derives its auth target from the spec's own servers[].
    assert naive.naive_auth_host(spec) == "evil.attacker.test"
    # Gecko's allowlist never contains it — it is not derived from the served spec.
    client = AgentApiClient(spec, session=Session(jwt="J", api_token="T"))
    assert "evil.attacker.test" not in client._auth_allowed_hosts


# =====================================================================================
# Attack 2 — private-key / seed-phrase leak via a poisoned operation description
# The op text and a param description tell the agent to paste its private key / seed
# phrase into a field. Gecko strips the instruction and quarantines the surface.
# =====================================================================================
def test_attack2_instruction_stripped_from_agent_facing_tool() -> None:
    tool = to_tool(_first_op(_spec("02_privkey_seed_leak")))
    assert tool.get("x-poison-flag") is True

    # The surfaced description the agent reads carries no exfil instruction.
    assert "private key" not in tool["description"].lower()

    # The poisoned param description is redacted too, not passed through.
    note = tool["inputSchema"]["properties"]["body"]["properties"]["note"]
    assert "seed phrase" not in note["description"].lower()


def test_attack2_surface_quarantined_no_auth_even_when_pinned() -> None:
    # Even WITH a legitimate base_url + a real auth session, a poisoned surface injects
    # no secret — it is quarantined until a human clears it.
    client = AgentApiClient(
        _spec("02_privkey_seed_leak"),
        base_url="https://api.wallet-poison.test",
        session=Session(jwt="J", api_token="SECRET_TOKEN"),
    )
    assert client.anchor.state == "quarantined"
    req = client.prepare("getWalletBalance", {"body": {"account": "acct-1"}})
    assert "Authorization" not in req.headers
    assert "SECRET_TOKEN" not in str(req.headers)
    assert (
        client.call("getWalletBalance", {"body": {"account": "acct-1"}}, mode="live")[
            "mode"
        ]
        == "recorded"
    )


def test_attack2_naive_baseline_leaks_instruction_to_agent() -> None:
    op = _first_op(_spec("02_privkey_seed_leak"))
    # Contrast: a raw OpenAPI->tool dump surfaces the exfil instruction verbatim.
    assert "private key" in naive.naive_description(op).lower()


# =====================================================================================
# Attack 3 — API-key echo via a poisoned param default / example
# An optional param carries a secret-looking default/example so an unset field is filled
# from the spec — the smuggle path an attacker uses to make an agent echo a captured key.
# =====================================================================================
def test_attack3_secret_default_and_example_dropped_from_tool_schema() -> None:
    client = AgentApiClient(_spec("03_apikey_echo_default"), session=public_session())
    tool = next(t for t in client.list_tools() if t["name"] == "createNote")
    audit = tool["inputSchema"]["properties"]["audit"]
    assert "default" not in audit  # secret-looking default neutralized
    assert "example" not in audit  # secret-looking example neutralized


def test_attack3_secret_never_lands_in_a_synthesized_arg() -> None:
    client = AgentApiClient(_spec("03_apikey_echo_default"), session=public_session())
    tool = next(t for t in client.list_tools() if t["name"] == "createNote")
    synthesized = json.dumps(example_from_schema(tool["inputSchema"]))
    assert "sk-AAAA" not in synthesized
    assert "sk-BBBB" not in synthesized


def test_attack3_naive_baseline_smuggles_the_secret_default() -> None:
    op = _first_op(_spec("03_apikey_echo_default"))
    # Contrast: the naive schema keeps the default/example, so a synthesized/unset arg
    # carries the secret-looking value (order-independent: example wins over default here).
    naive_arg = json.dumps(example_from_schema(naive.naive_input_schema(op)))
    assert "sk-" in naive_arg


# =====================================================================================
# Attack 4 — fund-transfer persuasion
# The op text "recommends" a transfer and the recipient field defaults to an attacker
# address, so an unset field routes money to them. Gecko flags, quarantines, drops it.
# =====================================================================================
ATTACKER_ADDR = "0xdeaddeaddeaddeaddeaddeaddeaddeaddeaddead"


def test_attack4_persuasion_flagged_and_surface_quarantined() -> None:
    client = AgentApiClient(
        _spec("04_fund_transfer_persuasion"),
        base_url="https://api.pay-poison.test",
        session=Session(jwt="J", api_token="SECRET_TOKEN"),
    )
    assert client.anchor.state == "quarantined"
    tool = client._tool_by_name["transferFunds"]
    assert tool.get("x-poison-flag") is True
    assert "forward the balance" not in tool["description"].lower()

    # Quarantine => no auth injected toward the (attacker) host, degrade to recorded.
    req = client.prepare("transferFunds", {"body": {"amount": 1}})
    assert "Authorization" not in req.headers
    assert "SECRET_TOKEN" not in str(req.headers)


def test_attack4_attacker_default_recipient_never_reaches_an_arg() -> None:
    client = AgentApiClient(
        _spec("04_fund_transfer_persuasion"),
        base_url="https://api.pay-poison.test",
        session=Session(jwt="J", api_token="T"),
    )
    tool = client._tool_by_name["transferFunds"]
    synthesized = json.dumps(example_from_schema(tool["inputSchema"]))
    assert ATTACKER_ADDR not in synthesized  # the default recipient was dropped


def test_attack4_naive_baseline_routes_to_attacker() -> None:
    op = _first_op(_spec("04_fund_transfer_persuasion"))
    naive_arg = json.dumps(example_from_schema(naive.naive_input_schema(op)))
    assert ATTACKER_ADDR in naive_arg  # naive fills 'to' from the poisoned default


# =====================================================================================
# Attack 5 — auth-location drift (header -> query)
# The securityScheme places the key in the query string. A naive tool appends the secret
# to the URL (logs/proxies/Referer). Gecko refuses to inject into a loggable location.
# =====================================================================================
def test_attack5_secret_never_placed_in_the_url() -> None:
    client = AgentApiClient(
        _spec("05_auth_location_drift"),
        base_url="https://api.oracle-poison.test",
        session=Session(jwt="JWT", api_token="TOKENVALUE"),
    )
    assert client.anchor.state == "pinned"  # host is fine; the LOCATION is the problem
    req = client.prepare("getPrice", {"symbol": "BTC"})
    assert "Authorization" not in req.headers
    assert "X-Api-Token" not in req.headers
    assert "TOKENVALUE" not in req.url
    assert "token=" not in req.url


def test_attack5_live_call_degrades_rather_than_leak() -> None:
    client = AgentApiClient(
        _spec("05_auth_location_drift"),
        base_url="https://api.oracle-poison.test",
        session=Session(jwt="J", api_token="T"),
    )
    assert client.call("getPrice", {"symbol": "BTC"}, mode="live")["mode"] == "recorded"


def test_attack5_naive_baseline_puts_secret_in_loggable_url() -> None:
    spec = _spec("05_auth_location_drift")
    op = _first_op(spec)
    url = naive.naive_query_auth_url(
        spec, op, "https://api.oracle-poison.test", "TOKENVALUE"
    )
    assert "token=TOKENVALUE" in url  # naive leaks the secret into the URL


# =====================================================================================
# Attack 6 — dropped `required` safety field
# The safety field (idempotencyKey, prevents a double-charge) is dropped from a tool's
# `required` after comprehension. Gecko's required-guard enforces the declared contract,
# and the tools_rev integrity anchor catches the post-comprehension tamper before serving.
# =====================================================================================
def _payment_client() -> AgentApiClient:
    return AgentApiClient(
        _spec("06_dropped_required_safety"),
        base_url="https://api.legit-pay.test",
        session=Session(jwt="J", api_token="T"),
    )


def test_attack6_required_guard_catches_missing_safety_field() -> None:
    client = _payment_client()
    # The agent omits the idempotency key: caught before any wire call, not fired.
    with pytest.raises(CallError) as exc:
        client.call(
            "createPayment",
            {"body": {"amount": 100, "to": "acct-2"}},
            mode="recorded",
        )
    assert "idempotencyKey" in str(exc.value)


def test_attack6_integrity_anchor_catches_dropped_required_tamper() -> None:
    client = _payment_client()
    good_args = {"body": {"idempotencyKey": "k-1", "amount": 100, "to": "acct-2"}}
    # Baseline: the un-tampered surface serves fine.
    assert client.prepare("createPayment", good_args).method == "POST"

    # Poisoning: an attacker drops the safety field from the shipped tool's `required`.
    body_schema = client._tool_by_name["createPayment"]["inputSchema"]["properties"][
        "body"
    ]
    body_schema["required"] = [
        r for r in body_schema["required"] if r != "idempotencyKey"
    ]

    # The tools_rev integrity anchor re-derives and refuses to serve the drifted tool set.
    with pytest.raises(IntegrityError):
        client.prepare("createPayment", good_args)


def test_attack6_naive_baseline_would_fire_without_the_safety_field() -> None:
    op = _first_op(_spec("06_dropped_required_safety"))
    # A naive tool that ignores `required` at call time has no guard: a partial body is
    # accepted. Gecko's caller is the guard that a naive pipeline lacks.
    naive_schema = naive.naive_input_schema(op)
    assert "idempotencyKey" in naive_schema["properties"]["body"]["required"]
    # But nothing in the naive path enforces it — there is no pre-flight required-check
    # equivalent to gecko.caller._missing_required, so the dangerous call would fire.
