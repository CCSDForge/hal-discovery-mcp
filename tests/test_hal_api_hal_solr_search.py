import pytest

from hal_api.api_hal_solr_search import MAX_FIELD_CHARS, hal_solr_search, validate_params


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
        {"q": "*:*", "start": 0, "cursorMark": "*"},
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
    ],
)
def test_validate_params_rejects_facets_unsafe_or_oversized_requests(params):
    with pytest.raises(ValueError):
        validate_params(params)


async def test_hal_solr_search_rejects_unknown_endpoint_without_calling_hal(fake_httpx):
    client = fake_httpx(json_data={})

    result = await hal_solr_search("ref/../update", {"q": "*:*"})

    assert "error" in result
    assert client.calls == []


async def test_hal_solr_search_sends_params_and_parses_response(fake_httpx):
    client = fake_httpx(
        url="https://api.archives-ouvertes.fr/search/?q=x",
        json_data={
            "response": {"numFound": 42, "docs": [{"halId_s": "hal-1", "abstract_s": ["a" * 5000]}]},
            "nextCursorMark": "AoE",
        },
    )

    result = await hal_solr_search("search", {"q": "llm", "fq": ["producedDateY_i:[2022 TO *]"]})

    sent = client.calls[0]
    assert sent["url"] == "https://api.archives-ouvertes.fr/search/"
    assert sent["params"]["fq"] == ["producedDateY_i:[2022 TO *]"]
    assert sent["params"]["rows"] == "10"
    assert sent["params"]["wt"] == "json"

    assert result["num_found"] == 42
    assert len(result["docs"][0]["abstract_s"][0]) < MAX_FIELD_CHARS + 10
    assert result["next_cursor_mark"] == "AoE"
    assert result["query_url"] == "https://api.archives-ouvertes.fr/search/?q=x"
    assert result["readable_url"].startswith("https://api.archives-ouvertes.fr/search/?q=llm&fq=producedDateY_i:[2022 TO *]")
    assert result["readable_url"].endswith("&wt=json")


async def test_hal_solr_search_reports_solr_syntax_error_with_sent_params(fake_httpx):
    fake_httpx(json_data={"error": {"msg": "Cannot parse 'x AND ('"}})

    result = await hal_solr_search("search", {"q": "x AND ("})

    assert "Cannot parse" in result["error"]
    assert result["solr_params"]["q"] == "x AND ("


async def test_hal_solr_search_queries_referentials(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 1, "docs": [{"docid": 1}]}})

    await hal_solr_search("ref/structure", {"q": "acronym_s:CCSD", "fl": "*"})

    assert client.calls[0]["url"] == "https://api.archives-ouvertes.fr/ref/structure/"



async def test_hal_solr_search_adds_aggregations_and_counts_on_same_q_and_fq(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {"numFound": 1, "docs": [{"authFullNameIdHal_fs": ["Yolande Maury_FacetSep_yolande-maury"]}]},
            "nextCursorMark": "c1",
        }
    )

    result = await hal_solr_search(
        "search",
        {"q": "llm", "fq": "docType_s:ART", "rows": 0},
        aggregate=["authFullNameIdHal_fs"],
        count_by={"2024": "producedDateY_i:2024"},
    )

    # 1 recherche + 1 page d'agrégation (num_found atteint) + 1 comptage.
    assert len(client.calls) == 3
    assert all(c["params"]["q"] == "llm" for c in client.calls)
    assert all(c["params"]["fq"][0] == "docType_s:ART" for c in client.calls[1:])
    assert not any(k.startswith("facet") for c in client.calls for k in c["params"])
    assert result["aggregations"]["fields"]["authFullNameIdHal_fs"]["top"] == [
        {"value": "Yolande Maury | yolande-maury", "count": 1}
    ]
    assert result["counts"]["2024"]["num_found"] == 1
    assert "verification_url" in result


@pytest.mark.parametrize(
    "endpoint, kwargs",
    [
        ("ref/author", {"aggregate": ["docType_s"]}),
        ("search", {"aggregate": ["a,b"]}),
        ("search", {"aggregate": ["docType_s"], "aggregate_max_docs": 10000}),
        ("search", {"count_by": {str(y): f"producedDateY_i:{y}" for y in range(1990, 2030)}}),
        ("search", {"count_by": {"vide": " "}}),
    ],
)
async def test_hal_solr_search_rejects_invalid_options_without_calling_hal(fake_httpx, endpoint, kwargs):
    client = fake_httpx(json_data={})

    result = await hal_solr_search(endpoint, {"q": "x"}, **kwargs)

    assert "error" in result
    assert client.calls == []


async def test_hal_solr_search_returns_printable_solr_queries(fake_httpx):
    fake_httpx(
        url="https://api.archives-ouvertes.fr/search/?q=llm&rows=0&wt=json",
        json_data={"response": {"numFound": 1, "docs": [{"docType_s": "ART"}]}},
    )

    result = await hal_solr_search(
        "search", {"q": "llm", "rows": 0}, aggregate=["docType_s"], count_by={"2024": "producedDateY_i:2024"}
    )

    block = result["solr_queries"]
    assert "https://api.archives-ouvertes.fr/search/?q=llm&rows=0&wt=json" in block
    assert "(numFound = 1)" in block
    assert "classement" in block and "comptes" in block
    assert "- 2024 (`fq=producedDateY_i:2024`) : 1" in block


async def test_server_instructions_require_showing_solr_queries():
    from core.mcp import mcp

    assert "solr_queries" in mcp.instructions


def test_validate_params_accepts_plain_fields_and_sorts():
    params = validate_params({"q": "x", "fl": "halId_s, title_s,score", "sort": "producedDate_tdate desc, docid asc", "df": "title_t"})

    assert params["fl"] == "halId_s, title_s,score"


async def test_hal_solr_search_aggregates_most_recent_docs_without_thematic_query(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 1, "docs": [{"docType_s": "ART"}]}})

    result = await hal_solr_search("search", {"q": "*:*", "fq": "structId_i:1"}, aggregate=["docType_s"])

    aggregation_call = next(c for c in client.calls if "cursorMark" in c["params"])
    assert aggregation_call["params"]["sort"] == "producedDate_tdate desc,docid asc"
    assert result["aggregations"]["order"] == "most_recent"
