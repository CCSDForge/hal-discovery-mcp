import hal_tools.get_publication_statistics_by_structure as tool_module
from hal_tools.get_publication_statistics_by_structure import get_publication_statistics_by_structure


async def test_rejects_inverted_period():
    result = await get_publication_statistics_by_structure(struct_id=1, start_year=2023, end_year=2020)

    assert "error" in result


async def test_aggregates_publications_by_year_and_type(monkeypatch):
    async def fake_search(struct_id, start_year, end_year):
        return {
            "num_found": 3,
            "total_returned": 3,
            "has_more": False,
            "publications": [
                {"year": 2020, "type": "ART"},
                {"year": 2020, "type": "ART"},
                {"year": None, "type": None},
            ],
            "query_url": "url",
        }

    monkeypatch.setattr(tool_module, "search_publication_stats", fake_search)

    result = await get_publication_statistics_by_structure(struct_id=194495, start_year=2018, end_year=2023)

    assert result["stats"] == {2020: {"ART": 2}, "UNKNOWN": {"UNKNOWN": 1}}
    assert result["period"] == "2018-2023"


async def test_propagates_api_error(monkeypatch):
    async def fake_search(struct_id, start_year, end_year):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(tool_module, "search_publication_stats", fake_search)

    result = await get_publication_statistics_by_structure(struct_id=194495, start_year=2018, end_year=2023)

    assert result == {"error": "boom", "query_url": None}
