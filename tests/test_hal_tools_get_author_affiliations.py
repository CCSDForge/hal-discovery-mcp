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
        return {"primary_structures_by_frequency": [], "num_found": 0, "id": id_hal}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)
    monkeypatch.setattr(tool_module, "api_get_author_affiliations", fake_affiliations)

    result = await get_author_affiliations("Jean Dupont")

    assert "homonyms_warning" in result
    by_author = result["affiliations_by_author"]
    assert set(by_author) == {"jean-dupont-1", "jean-dupont-2"}
    # chaque résultat est bien rattaché au bon hal_id malgré l'exécution en parallèle
    assert by_author["jean-dupont-2"]["id"] == "jean-dupont-2"


async def test_get_author_affiliations_queries_each_hal_id_once(monkeypatch):
    calls = []

    async def fake_search_author(name):
        # Le référentiel renvoie une ligne par forme auteur : même hal_id deux fois.
        return {
            "authors": [
                {"name": "Yutong Fei", "hal_id": "yutong-fei"},
                {"name": "Yutong FEI", "hal_id": "yutong-fei"},
            ],
            "query_url": "url",
        }

    async def fake_affiliations(id_hal, rows=100):
        calls.append(id_hal)
        return {"primary_structures_by_frequency": [], "num_found": 0}

    monkeypatch.setattr(tool_module, "_search_author", fake_search_author)
    monkeypatch.setattr(tool_module, "api_get_author_affiliations", fake_affiliations)

    result = await get_author_affiliations("Yutong Fei")

    assert calls == ["yutong-fei"]
    assert list(result["affiliations_by_author"]) == ["yutong-fei"]


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
