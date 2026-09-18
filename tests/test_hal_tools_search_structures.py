import hal_tools.search_structures as tool_module
from hal_tools.search_structures import search_structures


async def test_search_structures_rejects_empty_name():
    result = await search_structures("   ")

    assert "error" in result


async def test_search_structures_adds_warning_when_more_results_available(monkeypatch):
    async def fake_search(nom_structure, rows):
        return {
            "num_found": 5,
            "structures": [{"id": 1}],
            "structures_valides": [{"id": 1}],
            "structures_incoming": [],
            "structures_autres_statuts": [],
            "query_url": "url",
        }

    monkeypatch.setattr(tool_module, "_search_structure", fake_search)

    result = await search_structures("Lyon 1", rows=1)

    assert result["has_more"] is True
    assert "warning" in result


async def test_search_structures_clamps_rows_to_at_least_one(monkeypatch):
    captured = {}

    async def fake_search(nom_structure, rows):
        captured["rows"] = rows
        return {
            "num_found": 0,
            "structures": [],
            "structures_valides": [],
            "structures_incoming": [],
            "structures_autres_statuts": [],
            "query_url": "url",
        }

    monkeypatch.setattr(tool_module, "_search_structure", fake_search)

    await search_structures("Lyon 1", rows=0)

    assert captured["rows"] == 1
