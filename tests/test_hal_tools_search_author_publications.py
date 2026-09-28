from datetime import date

import hal_tools.search_author_publications as tool_module
from hal_tools.search_author_publications import search_author_publications


async def test_search_author_publications_requires_name_or_hal_id():
    result = await search_author_publications(author_name="  ", hal_id=None)

    assert "error" in result


async def test_search_author_publications_rejects_inverted_period():
    result = await search_author_publications(
        hal_id="yutong-fei", start_date=date(2023, 1, 1), end_date=date(2020, 1, 1)
    )

    assert "error" in result


async def test_search_author_publications_counts_abstracts(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {
            "num_found": 10,
            "total_returned": 2,
            "has_more": True,
            "publications": [
                {"title": "A", "abstract": "un resume"},
                {"title": "B", "abstract": None},
            ],
            "verification_url": "url-verif",
            "query_url": "url",
        }

    monkeypatch.setattr(tool_module, "_search_author_publications", fake_search)

    result = await search_author_publications(hal_id=" yutong-fei ")

    assert captured["hal_id"] == "yutong-fei"
    assert result["num_found"] == 10
    assert result["has_more"] is True
    assert result["with_abstract"] == 1
    assert result["without_abstract"] == 1
    assert result["verification_url"] == "url-verif"


async def test_search_author_publications_propagates_api_error(monkeypatch):
    async def fake_search(**kwargs):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(tool_module, "_search_author_publications", fake_search)

    result = await search_author_publications(author_name="Yutong Fei")

    assert result == {"error": "boom", "query_url": None}