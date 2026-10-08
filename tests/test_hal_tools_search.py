import pytest
from mcp.server.mcpserver.exceptions import ToolError

import hal_tools.search as tool_module
import server  # noqa: F401  (enregistre les outils)
from core.mcp import mcp


async def test_search_tool_passes_endpoint_and_params(monkeypatch):
    captured = {}

    async def fake_search(endpoint, params):
        captured.update(endpoint=endpoint, params=params)
        return {"num_found": 0, "docs": [], "query_url": "u"}

    monkeypatch.setattr(tool_module, "_search", fake_search)

    await mcp.call_tool("search", {"params": {"q": "*:*", "fq": ["docType_s:ART"]}})

    assert captured == {"endpoint": "search", "params": {"q": "*:*", "fq": ["docType_s:ART"]}}


async def test_search_tool_rejects_unlisted_endpoint_before_calling_hal():
    with pytest.raises(ToolError):
        await mcp.call_tool("search", {"endpoint": "admin", "params": {"q": "*:*"}})


@pytest.mark.parametrize("option", ["aggregate", "count_by"])
async def test_search_tool_no_longer_exposes_calculations(option):
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    assert option not in tools["search"].input_schema["properties"]
