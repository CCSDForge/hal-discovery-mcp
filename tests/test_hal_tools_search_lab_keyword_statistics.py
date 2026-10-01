import hal_tools.search_lab_keyword_statistics as tool_module
from hal_tools.search_lab_keyword_statistics import search_lab_keyword_statistics


async def test_search_lab_keyword_statistics_passes_limit(monkeypatch):
    captured = {}

    async def fake_search(struct_id, year, limit=30):
        captured.update(struct_id=struct_id, year=year, limit=limit)
        return {"keyword_aggregation": {}}

    monkeypatch.setattr(tool_module, "search_lab_keywords", fake_search)

    await search_lab_keyword_statistics(struct_id=194495, year=2023, limit=5)

    assert captured == {"struct_id": 194495, "year": 2023, "limit": 5}
