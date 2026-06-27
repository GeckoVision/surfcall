"""surfcall — make any API agent-usable without integration code.

V1 = the comprehension layer: ingest a human-shaped OpenAPI surface and emit
question-shaped, first-call-correct agent tools. No data is ingested — only the
API's public capability surface (endpoints, params, schemas). The agent calls
the upstream API directly for data.
"""

__version__ = "0.1.0"
