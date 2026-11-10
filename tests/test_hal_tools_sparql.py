import pytest
from mcp.server.mcpserver.exceptions import ToolError

import hal_tools.build_network as network_module
import hal_tools.sparql as sparql_module
import server  # noqa: F401  (enregistre les outils)
from core.mcp import mcp


async def tools_by_name():
    return {tool.name: tool for tool in await mcp.list_tools()}


async def test_sparql_tool_passes_query(monkeypatch):
    captured = {}

    async def fake(query):
        captured["query"] = query
        return {"rows": []}

    monkeypatch.setattr(sparql_module, "_sparql", fake)

    await mcp.call_tool("sparql", {"query": "SELECT ?s WHERE { ?s ?p ?o }"})

    assert captured == {"query": "SELECT ?s WHERE { ?s ?p ?o }"}


async def test_build_network_tool_passes_query_and_min_docs(monkeypatch):
    captured = {}

    async def fake(query, min_docs):
        captured.update(query=query, min_docs=min_docs)
        return {}

    monkeypatch.setattr(network_module, "_build_network", fake)

    await mcp.call_tool("build_network", {"query": "SELECT ?doc ?item WHERE { }", "min_docs": 3})

    assert captured == {"query": "SELECT ?doc ?item WHERE { }", "min_docs": 3}


async def test_build_network_min_docs_is_bounded_before_calling_hal():
    with pytest.raises(ToolError):
        await mcp.call_tool("build_network", {"query": "SELECT ?doc ?item WHERE { }", "min_docs": 0})


@pytest.mark.parametrize("tool_name", ["sparql", "build_network"])
async def test_sparql_tools_describe_the_hal_data_model(tool_name):
    description = (await tools_by_name())[tool_name].description

    assert "dc:subject" in description
    assert "ore:isAggregatedBy" in description
    assert "bif:contains" in description
