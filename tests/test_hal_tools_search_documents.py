import pytest
from mcp.server.mcpserver.exceptions import ToolError

import hal_tools.search_documents as tool_module
from core.mcp import mcp
from hal_tools.search_documents import search_documents


async def test_forwards_parameters(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {"num_found": 0, "docs": []}

    monkeypatch.setattr(tool_module, "_search_documents", fake_search)

    await search_documents(q="x", fq=["docType_s:ART"], sort="docid asc", rows=5, fl=["halId_s"])

    assert captured == {"q": "x", "fq": ["docType_s:ART"], "sort": "docid asc", "rows": 5, "fl": ["halId_s"]}


async def test_rows_above_limit_is_rejected_by_mcp():
    with pytest.raises(ToolError):
        await mcp.call_tool("search_documents", {"q": "x", "rows": 101})
