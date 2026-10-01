from urllib.parse import parse_qs, urlparse

from hal_api.api_search_lab_keyword_statistics import search_lab_keywords


async def test_search_lab_keywords_aggregates_solr_facets(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {"numFound": 120},
            "facet_counts": {
                "facet_fields": {
                    "keyword_s": ["intelligence artificielle", 42, "biologie", 30],
                }
            },
        }
    )

    result = await search_lab_keywords(194495, 2023, limit=10)

    assert result["struct_id"] == 194495
    assert result["year"] == 2023
    assert result["total_publications"] == 120
    assert result["keyword_aggregation"] == {"intelligence artificielle": 42, "biologie": 30}
    assert result["query_url"]
    assert client.calls[0]["params"]["facet.limit"] == 10

    urls = result["verification_urls"]
    assert parse_qs(urlparse(urls["all"]).query)["fq"] == ["structId_i:194495", "producedDateY_i:2023"]
    assert set(urls["by_keyword"]) == {"intelligence artificielle", "biologie"}
    kw_fq = parse_qs(urlparse(urls["by_keyword"]["biologie"]).query)["fq"]
    assert kw_fq == ["structId_i:194495", "producedDateY_i:2023", 'keyword_s:"biologie"']


async def test_search_lab_keywords_caps_number_of_keyword_links(fake_httpx):
    facet = []
    for i in range(50):
        facet += [f"mot{i}", 50 - i]
    fake_httpx(json_data={"response": {"numFound": 1}, "facet_counts": {"facet_fields": {"keyword_s": facet}}})

    result = await search_lab_keywords(194495, 2023, limit=50)

    assert len(result["keyword_aggregation"]) == 50
    assert list(result["verification_urls"]["by_keyword"]) == [f"mot{i}" for i in range(30)]


async def test_search_lab_keywords_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=500, text_data="internal error")

    result = await search_lab_keywords(194495, 2023)

    assert "500" in result["error"]
    assert result["query_url"]


async def test_search_lab_keywords_tolerates_missing_blocks(fake_httpx):
    fake_httpx(json_data={})

    result = await search_lab_keywords(194495, 2023)

    assert result["total_publications"] == 0
    assert result["keyword_aggregation"] == {}
