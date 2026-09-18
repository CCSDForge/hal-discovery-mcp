import hal_tools.search_authors as tool_module
from hal_tools.search_authors import search_authors


async def test_search_authors_rejects_empty_query():
    result = await search_authors("   ")

    assert result == {"error": "Le paramètre 'query' est requis et ne peut pas être vide"}


async def test_search_authors_strips_query_and_passes_through_api_result(monkeypatch):
    async def fake_api(query, rows=10):
        assert query == "Yutong Fei"
        return {"num_found": 1, "authors": [{"name": "Yutong Fei"}], "query_url": "url"}

    monkeypatch.setattr(tool_module, "search_authors_api", fake_api)

    result = await search_authors("  Yutong Fei  ")

    assert result["authors"] == [{"name": "Yutong Fei"}]


async def test_search_authors_propagates_api_error(monkeypatch):
    async def fake_api(query, rows=10):
        return {"error": "boom", "query_url": "url"}

    monkeypatch.setattr(tool_module, "search_authors_api", fake_api)

    result = await search_authors("query")

    assert result == {"error": "boom", "query_url": "url"}
