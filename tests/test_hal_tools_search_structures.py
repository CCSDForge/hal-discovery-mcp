import hal_tools.search_structures as tool_module
from hal_tools.search_structures import search_structures


def api_result(num_found, structures):
    return {
        "num_found": num_found,
        "structures": structures,
        "structures_valid": structures,
        "structures_incoming": [],
        "structures_other_status": [],
        "query_url": "url",
    }


async def test_search_structures_rejects_empty_name():
    result = await search_structures("   ")

    assert "error" in result


async def test_search_structures_adds_warning_when_more_results_available(monkeypatch):
    async def fake_search(structure_name, rows):
        return api_result(5, [{"id": 1}])

    monkeypatch.setattr(tool_module, "_search_structure", fake_search)

    result = await search_structures("Lyon 1", rows=1)

    assert result["has_more"] is True
    assert result["total_returned"] == 1
    assert result["structures_valid"] == [{"id": 1}]
    assert "rows" in result["warning"]


async def test_search_structures_warning_at_max_rows_asks_for_more_precise_search(monkeypatch):
    async def fake_search(structure_name, rows):
        return api_result(500, [{"id": i} for i in range(rows)])

    monkeypatch.setattr(tool_module, "_search_structure", fake_search)

    result = await search_structures("CNRS", rows=tool_module.MAX_ROWS)

    assert "Précise la recherche" in result["warning"]


async def test_search_structures_no_warning_when_complete(monkeypatch):
    async def fake_search(structure_name, rows):
        return api_result(1, [{"id": 1}])

    monkeypatch.setattr(tool_module, "_search_structure", fake_search)

    result = await search_structures("Lyon 1")

    assert result["has_more"] is False
    assert "warning" not in result