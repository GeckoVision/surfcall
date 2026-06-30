from pathlib import Path

from gecko.catalog import Catalog, CatalogEntry
from gecko.client import AgentApiClient
from gecko.ingest import Operation, extract_operations, load_spec
from gecko.tools import to_tool

FIXTURE = Path(__file__).parent / "fixtures" / "txodds_docs.yaml"


def _catalog() -> Catalog:
    return Catalog(extract_operations(load_spec(str(FIXTURE))))


def test_search_live_odds_finds_odds_endpoint():
    res = _catalog().search("live odds for a fixture")
    assert res, "expected results for a clear intent"
    assert "Odds" in res[0].operation.tags
    assert "odds" in res[0].operation.path


def test_search_scores_in_top_results():
    res = _catalog().search("match score updates")
    assert any("Scores" in e.operation.tags for e in res[:3])


def test_by_tag_covers_all_operations():
    grouped = _catalog().by_tag()
    assert {"Authentication", "Fixtures", "Odds", "Scores"} <= set(grouped)
    assert sum(len(v) for v in grouped.values()) == 18


def test_describe_renders_capability_map():
    text = _catalog().describe()
    assert "/api/odds/" in text
    assert "## Odds" in text


def test_empty_query_returns_nothing():
    assert _catalog().search("") == []


# FIX 1 — single source of truth for the tool name. When an op has no operationId,
# ingest synthesizes "post_/api/v1/charge"; to_tool sanitizes it but the catalog used
# to return the RAW id, so client.search (which filters on sanitized names) dropped
# every result. tool_name must agree across both layers.
def test_catalog_tool_name_matches_to_tool_for_synthesized_id():
    op = Operation(
        method="POST",
        path="/api/v1/charge",
        operation_id="post_/api/v1/charge",  # what ingest synthesizes (no operationId)
        summary="Create a new charge",
        description="",
        tags=[],
        parameters=[],
        request_body=None,
        responses={},
    )
    assert CatalogEntry(op).tool_name == to_tool(op)["name"]


SPEC_NO_OPID = {
    "openapi": "3.1.0",
    "servers": [{"url": "https://api.example.test"}],
    "paths": {
        "/api/v1/charge": {
            "post": {
                "summary": "Create a new charge",
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}


def test_search_finds_operation_without_operation_id():
    client = AgentApiClient(SPEC_NO_OPID)
    hits = client.search("create charge")
    assert hits, "search must return a hit for an op that has no operationId"
