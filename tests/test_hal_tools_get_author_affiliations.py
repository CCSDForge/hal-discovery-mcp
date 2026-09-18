import hal_tools.get_author_affiliations as tool_module
from hal_tools.get_author_affiliations import get_author_affiliations


async def test_get_author_affiliations_rejects_empty_name():
    result = await get_author_affiliations("   ")

    assert "error" in result


async def test_get_author_affiliations_reports_no_author_found(monkeypatch):
    async def fake_search_author(name):
        return {"authors": [], "query_url": "url"}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)

    result = await get_author_affiliations("Unknown Person")

    assert result["authors_found"] == []
    assert "Unknown Person" in result["message"]


async def test_get_author_affiliations_warns_on_homonyms(monkeypatch):
    async def fake_search_author(name):
        return {
            "authors": [
                {"name": "Jean Dupont", "hal_id": "jean-dupont-1"},
                {"name": "Jean Dupont", "hal_id": "jean-dupont-2"},
            ],
            "query_url": "url",
        }

    async def fake_affiliations(id_hal, rows=100):
        return {"primary_structures_by_frequency": [], "num_found": 0}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)
    monkeypatch.setattr(tool_module, "api_get_author_affiliations", fake_affiliations)

    result = await get_author_affiliations("Jean Dupont")

    assert "homonyms_warning" in result
    assert set(result["affiliations_by_author"].keys()) == {"jean-dupont-1", "jean-dupont-2"}


async def test_get_author_affiliations_reports_explicit_error_when_hal_id_missing(monkeypatch):
    async def fake_search_author(name):
        return {"authors": [{"name": "No Id Author", "hal_id": None}], "query_url": "url"}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)

    result = await get_author_affiliations("No Id Author")

    entry = result["affiliations_by_author"]["No Id Author"]
    assert "error" in entry


async def test_get_author_affiliations_propagates_author_search_error(monkeypatch):
    async def fake_search_author(name):
        return {"error": "hal down", "query_url": None}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)

    result = await get_author_affiliations("Someone")

    assert result == {"error": "hal down", "query_url": None}
