"""Tests for the TDD test generator (gecko.testgen)."""

from __future__ import annotations

from gecko import testgen

# A tiny spec: a no-required op, a required-body op, and a required-path-param op.
_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Tiny", "version": "1"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/widgets": {
            "get": {
                "operationId": "listWidgets",
                "summary": "list widgets",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    },
                                }
                            }
                        }
                    }
                },
            },
            "post": {
                "operationId": "createWidget",
                "summary": "create a widget",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "size": {"type": "integer"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "string"}},
                                }
                            }
                        }
                    }
                },
            },
        },
        "/widgets/{id}": {
            "get": {
                "operationId": "getWidget",
                "summary": "get a widget",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "string"}},
                                }
                            }
                        }
                    }
                },
            }
        },
    },
}


def test_check_all_pass_recorded() -> None:
    results = testgen.check(_SPEC)
    assert results, "expected generated checks"
    failed = [(r.tool, r.kind, r.detail) for r in results if not r.ok]
    assert not failed, f"unexpected failures: {failed}"


def test_well_formed_covers_every_usable_tool() -> None:
    well = {r.tool for r in testgen.check(_SPEC) if r.kind == "well_formed"}
    assert well == {"listWidgets", "createWidget", "getWidget"}


def test_required_guard_only_where_required_and_passes() -> None:
    guards = {r.tool: r for r in testgen.check(_SPEC) if r.kind == "required_guard"}
    # createWidget (required body) + getWidget (required path param); listWidgets has none.
    assert set(guards) == {"createWidget", "getWidget"}
    assert all(r.ok for r in guards.values())


def test_render_module_emits_compilable_pytest() -> None:
    src = testgen.render_module(
        "https://api.example.com/openapi.json", out_name="test_x.py"
    )
    assert "def test_first_call_well_formed" in src
    assert "def test_missing_required_is_caught" in src
    assert "https://api.example.com/openapi.json" in src
    compile(src, "test_x.py", "exec")  # the emitted module must at least compile
