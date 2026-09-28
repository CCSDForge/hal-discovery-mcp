import hal_tools.get_publication_statistics_by_structure as tool_module
from hal_tools.get_publication_statistics_by_structure import get_publication_statistics_by_structure


async def test_rejects_inverted_period():
    result = await get_publication_statistics_by_structure(struct_id=1, start_year=2023, end_year=2020)

    assert "error" in result


async def test_returns_stats_computed_by_hal(monkeypatch):
    async def fake_search(struct_id, start_year, end_year):
        return {
            "num_found": 3,
            "stats": {2020: {"ART": 2, "COMM": 1}},
            "verification_urls": {"all": "url-all", "by_year": {}, "by_doc_type": {}},
            "query_url": "url",
        }

    monkeypatch.setattr(tool_module, "search_publication_stats", fake_search)

    result = await get_publication_statistics_by_structure(struct_id=194495, start_year=2018, end_year=2023)

    assert result == {
        "struct_id": 194495,
        "period": "2018-2023",
        "num_found": 3,
        "stats": {2020: {"ART": 2, "COMM": 1}},
        "verification_urls": {"all": "url-all", "by_year": {}, "by_doc_type": {}},
        "query_url": "url",
    }


async def test_propagates_api_error(monkeypatch):
    async def fake_search(struct_id, start_year, end_year):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(tool_module, "search_publication_stats", fake_search)

    result = await get_publication_statistics_by_structure(struct_id=194495, start_year=2018, end_year=2023)

    assert result == {"error": "boom", "query_url": None}