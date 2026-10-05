import hal_tools.search_publications_by_topic as tool_module
from hal_api.api_search_publications_by_topic import DEFAULT_DOC_TYPES
from hal_tools.search_publications_by_topic import search_publications_by_topic


def capture(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {"num_found": 0, "publications": [], "verification_url": "v", "query_url": "q"}

    monkeypatch.setattr(tool_module, "_search_publications_by_topic", fake_search)
    return captured


async def test_rejects_empty_query():
    result = await search_publications_by_topic("   ")

    assert "error" in result


async def test_rejects_inverted_period():
    result = await search_publications_by_topic("x", start_year=2024, end_year=2020)

    assert "error" in result


async def test_defaults_to_scientific_doc_types(monkeypatch):
    captured = capture(monkeypatch)

    result = await search_publications_by_topic("  science ouverte  ")

    assert captured["doc_types"] == DEFAULT_DOC_TYPES
    assert captured["query"] == "science ouverte"
    assert result["query"] == "science ouverte"


async def test_empty_doc_types_means_all_types(monkeypatch):
    captured = capture(monkeypatch)

    await search_publications_by_topic("science ouverte", doc_types=[])

    assert captured["doc_types"] == []


async def test_propagates_api_error(monkeypatch):
    async def fake_search(**kwargs):
        return {"error": "boom", "query_url": None}

    monkeypatch.setattr(tool_module, "_search_publications_by_topic", fake_search)

    result = await search_publications_by_topic("x")

    assert result == {"error": "boom", "query_url": None}
