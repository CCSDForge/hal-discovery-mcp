from datetime import date

import hal_tools.search_structure_publications as tool_module
from hal_tools.search_structure_publications import search_structure_publications


async def test_rejects_inverted_period():
    result = await search_structure_publications([1], start_date=date(2025, 1, 1), end_date=date(2024, 1, 1))

    assert "error" in result


async def test_delegates_to_api_with_all_types_by_default(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {"num_found": 0}

    monkeypatch.setattr(tool_module, "_search_structure_publications", fake_search)

    await search_structure_publications([1005874, 154357])

    assert captured == {
        "struct_ids": [1005874, 154357],
        "start_date": None,
        "end_date": None,
        "doc_types": None,
        "rows": 10,
    }
