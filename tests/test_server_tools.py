"""
Vérifie ce que le serveur MCP expose réellement aux clients : la liste des
outils et les contraintes de paramètres (validées par MCP avant l'appel).
"""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server  # noqa: F401  (enregistre les outils)
from core.mcp import mcp

EXPECTED_TOOLS = {
    "search_authors",
    "search_author_publications",
    "get_author_affiliations",
    "search_structures",
    "search_publications_by_topic",
    "search_structure_publications",
    "get_structure_topics",
    "search_projects",
    "get_project_publications",
    "hal_solr_search",
}


async def tools_by_name():
    return {tool.name: tool for tool in await mcp.list_tools()}


async def test_all_tools_are_registered():
    assert set(await tools_by_name()) == EXPECTED_TOOLS


@pytest.mark.parametrize(
    "tool_name, param",
    [
        ("search_authors", "rows"),
        ("search_author_publications", "rows"),
        ("get_author_affiliations", "rows"),
        ("search_structures", "rows"),
        ("search_publications_by_topic", "rows"),
        ("search_structure_publications", "rows"),
        ("get_structure_topics", "top"),
        ("search_projects", "rows"),
        ("get_project_publications", "rows"),
        ("hal_solr_search", "aggregate_max_docs"),
        ("hal_solr_search", "aggregate_top"),
    ],
)
async def test_result_size_parameters_are_bounded(tool_name, param):
    schema = (await tools_by_name())[tool_name].input_schema["properties"][param]

    assert schema["minimum"] == 1
    assert "maximum" in schema


async def test_out_of_range_rows_is_rejected_before_calling_hal():
    with pytest.raises(ToolError):
        await mcp.call_tool("search_authors", {"query": "x", "rows": 100000})
