"""Priority 2 — from-docs surfaces are born quarantined (poisoned-until-proven).

A draft recovered from human docs is a guess: recorded-mode only, NO live auth injection,
until a human clears it. The rule is enforced in client/surfaces (not bolted into
docs_reader.emit), and a quarantined/unverified surface degrades gracefully rather than
hard-failing the agent on un-drifted ops.
"""

from __future__ import annotations

from gecko.access import Session, public_session
from gecko.client import AgentApiClient
from gecko.docs_reader import build_draft_openapi
from gecko.docs_reader.models import CandidateOp, CandidateParam
from gecko.surfaces import SurfaceRegistry, spec_is_quarantined

# A spec carrying the docs_reader generator stamp + an x-review note = a draft.
DRAFT_MARKER_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Recovered API", "x-generated-by": "gecko.docs_reader"},
    "servers": [{"url": "https://api.example.test"}],
    "components": {
        "securitySchemes": {
            "uuidAuth": {"type": "apiKey", "in": "header", "name": "X-Api-Key"}
        }
    },
    "paths": {
        "/getThing": {
            "post": {
                "operationId": "getThing",
                "summary": "Get a thing",
                "security": [{}, {"uuidAuth": []}],
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}


def test_spec_is_quarantined_detects_generator_marker():
    assert spec_is_quarantined(DRAFT_MARKER_SPEC) is True
    assert spec_is_quarantined({"openapi": "3.1.0", "paths": {}}) is False


def test_spec_is_quarantined_detects_review_and_low_confidence():
    assert spec_is_quarantined({"paths": {"/x": {"x-review": "confirm"}}}) is True
    assert spec_is_quarantined({"a": {"x-draft-confidence": "low"}}) is True
    assert spec_is_quarantined({"a": {"x-draft-confidence": "high"}}) is False


def test_from_docs_surface_born_quarantined_no_auth():
    # Even WITH a real base_url + an auth session, a draft injects no secret.
    client = AgentApiClient(
        DRAFT_MARKER_SPEC,
        base_url="https://api.example.test",
        session=Session(jwt="J", api_token="SECRET"),
    )
    assert client.anchor.state == "quarantined"
    req = client.prepare("getThing", {})
    assert "X-Api-Key" not in req.headers
    assert "Authorization" not in req.headers


def test_quarantined_surface_still_serves_undrifted_ops():
    # It degrades — it does not hard-fail. A public read still prepares fine.
    client = AgentApiClient(DRAFT_MARKER_SPEC, session=public_session())
    req = client.prepare("getThing", {})
    assert req.url.endswith("/getThing")
    result = client.call("getThing", {}, mode="live")  # live -> recorded degrade
    assert result["mode"] == "recorded"


def test_real_draft_from_docs_reader_is_quarantined():
    # A genuine docs_reader draft (low-confidence op) is quarantined by construction.
    op = CandidateOp(
        operation_id="getBalance",
        http_method="POST",
        http_path="/rpc",
        host="https://api.example.test",
        transport="jsonrpc",
        jsonrpc_method="getBalance",
        params=[CandidateParam(name="account", type="string", required=True)],
        summary="Get balance",
        confidence="low",
        review=["confirm the endpoint"],
    )
    draft = build_draft_openapi([op], "Recovered", ["https://docs.example/x"])
    assert spec_is_quarantined(draft) is True
    client = AgentApiClient(draft, session=Session(jwt="J", api_token="T"))
    assert client.anchor.state == "quarantined"


def test_registry_from_docs_is_quarantined_with_no_trusted_host():
    reg = SurfaceRegistry()
    s = reg.register(
        "draft", DRAFT_MARKER_SPEC, base_url="https://api.example.test", from_docs=True
    )
    assert s.state == "quarantined"
    assert s.trusted_hosts == frozenset()


def test_registry_pins_a_normal_surface_to_its_base_url_host():
    reg = SurfaceRegistry()
    s = reg.register(
        "ok",
        {"openapi": "3.1.0", "paths": {}},
        base_url="https://api.pegana.xyz",
    )
    assert s.state == "pinned"
    assert s.trusted_hosts == frozenset({"api.pegana.xyz"})
