import pytest
from mcp.server.mcpserver.exceptions import ToolError

import hal_tools.hal_solr_search as tool_module
import server  # noqa: F401  (enregistre les outils)
from core.mcp import mcp


async def test_search_tool_passes_endpoint_and_params(monkeypatch):
    captured = {}

    async def fake_search(endpoint, params, **options):
        captured.update(endpoint=endpoint, params=params, **options)
        return {"num_found": 0, "docs": [], "query_url": "u"}

    monkeypatch.setattr(tool_module, "_hal_solr_search", fake_search)

    await mcp.call_tool("hal_solr_search", {"params": {"q": "*:*", "fq": ["docType_s:ART"]}})

    assert captured == {
        "endpoint": "search",
        "params": {"q": "*:*", "fq": ["docType_s:ART"]},
        "aggregate": None,
        "aggregate_max_docs": 300,
        "aggregate_top": 15,
        "count_by": None,
    }


async def test_search_tool_rejects_unlisted_endpoint_before_calling_hal():
    with pytest.raises(ToolError):
        await mcp.call_tool("hal_solr_search", {"endpoint": "admin", "params": {"q": "*:*"}})

