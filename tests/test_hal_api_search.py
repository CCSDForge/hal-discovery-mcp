import pytest

from hal_api.api_search import MAX_FIELD_CHARS, search, validate_params


def test_validate_params_normalizes_values():
    params = validate_params({"q": "*:*", "rows": 0, "fq": ["docType_s:ART", "producedDateY_i:2024"]})

    assert params == {"q": "*:*", "rows": "0", "fq": ["docType_s:ART", "producedDateY_i:2024"]}


@pytest.mark.parametrize(
    "params",
    [
        {"fq": "docType_s:ART"},  # q manquant
        {"q": "*:*", "wt": "xml"},
        {"q": "*:*", "qt": "/update"},
        {"q": "*:*", "facet": "true", "facet.field": "authIdHal_s"},
        {"q": "*:*", "f.authIdHal_s.facet.limit": 5},
        {"q": "*:*", "group": "true"},
        {"q": "*:*", "stats": "true"},
        {"q": "*:*", "rows": 1000},
        {"q": "*:*", "rows": "10 OR 1"},
        # pas de pagination : l'agent affine sa requête
        {"q": "*:*", "start": 10},
        {"q": "*:*", "cursorMark": "*"},
        {"q": "*:*", "fq": []},
        {"q": "*:*", "fq": {"a": 1}},
        # paramètres locaux, fonctions et transformateurs : coût non borné pour HAL
        {"q": "{!join from=a to=b}x"},
        {"q": 'title_t:x AND _query_:"{!frange l=1}div(a,b)"'},
        {"q": "*:*", "fq": ["docType_s:ART", "{!collapse field=authIdHal_s}"]},
        {"q": "*:*", "fl": "title_s,[subquery]"},
        {"q": "*:*", "fl": "title_s,[explain]"},
        {"q": "*:*", "sort": "div(producedDateY_i,2) desc"},
        {"q": "*:*", "sort": "producedDate_tdate"},
        {"q": "*:*", "df": "title_t abstract_t"},
        {"q": "*:*", "q.op": "XOR"},
        # fl=* : coûteux pour HAL (mesuré)
        {"q": "*:*", "fl": "*"},  # rows=10 par défaut
        {"q": "*:*", "fl": "halId_s,*", "rows": 6},
    ],
)
def test_validate_params_rejects_facets_unsafe_or_oversized_requests(params):
    with pytest.raises(ValueError):
        validate_params(params)


async def test_search_rejects_unknown_endpoint_without_calling_hal(fake_httpx):
    client = fake_httpx(json_data={})

    result = await search("ref/../update", {"q": "*:*"})

    assert "error" in result
    assert client.calls == []


async def test_search_sends_params_and_parses_response(fake_httpx):
    client = fake_httpx(
        url="https://api.archives-ouvertes.fr/search/?q=x",
        json_data={
            "response": {"numFound": 42, "docs": [{"halId_s": "hal-1", "abstract_s": ["a" * 5000]}]},
        },
    )

    result = await search("search", {"q": "llm", "fq": ["producedDateY_i:[2022 TO *]"]})

    sent = client.calls[0]
    assert sent["url"] == "https://api.archives-ouvertes.fr/search/"
    assert sent["params"]["fq"] == ["producedDateY_i:[2022 TO *]"]
    assert sent["params"]["rows"] == "10"
    assert sent["params"]["wt"] == "json"

    assert result["num_found"] == 42
    assert len(result["docs"][0]["abstract_s"][0]) < MAX_FIELD_CHARS + 10
    assert result["query_url"] == "https://api.archives-ouvertes.fr/search/?q=x"
    assert result["readable_url"].startswith("https://api.archives-ouvertes.fr/search/?q=llm&fq=producedDateY_i:[2022 TO *]")
    assert result["readable_url"].endswith("&wt=json")


async def test_search_reports_solr_syntax_error_with_sent_params(fake_httpx):
    fake_httpx(json_data={"error": {"msg": "Cannot parse 'x AND ('"}})

    result = await search("search", {"q": "x AND ("})

    assert "Cannot parse" in result["error"]
    assert result["solr_params"]["q"] == "x AND ("


async def test_search_queries_referentials(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 1, "docs": [{"docid": 1}]}})

    await search("ref/structure", {"q": "acronym_s:CCSD", "fl": "*", "rows": 1})

    assert client.calls[0]["url"] == "https://api.archives-ouvertes.fr/ref/structure/"



async def test_search_returns_printable_solr_queries(fake_httpx):
    fake_httpx(
        url="https://api.archives-ouvertes.fr/search/?q=llm&rows=0&wt=json",
        json_data={"response": {"numFound": 1, "docs": [{"docType_s": "ART"}]}},
    )

    result = await search("search", {"q": "llm", "rows": 0})

    block = result["solr_queries"]
    assert "https://api.archives-ouvertes.fr/search/?q=llm&rows=0&wt=json" in block
    assert "(numFound = 1)" in block
    assert "[Ouvrir dans l'API HAL](https://api.archives-ouvertes.fr/search/?q=llm&rows=0&wt=json)" in block


async def test_server_instructions_require_showing_solr_queries():
    from core.mcp import mcp

    assert "solr_queries" in mcp.instructions


def test_validate_params_accepts_plain_fields_and_sorts():
    params = validate_params({"q": "x", "fl": "halId_s, title_s,score", "sort": "producedDate_tdate desc, docid asc", "df": "title_t"})

    assert params["fl"] == "halId_s, title_s,score"


def test_validate_params_allows_all_fields_only_to_discover_them():
    assert validate_params({"q": "*:*", "fl": "*", "rows": 5})["fl"] == "*"
