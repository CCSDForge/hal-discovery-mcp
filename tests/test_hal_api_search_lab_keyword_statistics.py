from hal_api.api_search_lab_keyword_statistics import search_lab_keywords


async def test_search_lab_keywords_aggregates_solr_facets(fake_aiohttp):
    fake_aiohttp(
        json_data={
            "response": {"numFound": 120},
            "facet_counts": {
                "facet_fields": {
                    "keyword_s": ["intelligence artificielle", 42, "biologie", 30],
                }
            },
        }
    )

    result = await search_lab_keywords("194495", 2023, limit=10)

    assert result["structure_id"] == "194495"
    assert result["year"] == 2023
    assert result["total_publications"] == 120
    assert result["keyword_aggregation"] == {"intelligence artificielle": 42, "biologie": 30}


async def test_search_lab_keywords_returns_error_on_non_200(fake_aiohttp):
    fake_aiohttp(status=500, text_data="internal error")

    result = await search_lab_keywords("194495", 2023)

    assert "500" in result["error"]


async def test_search_lab_keywords_returns_empty_aggregation_without_facets(fake_aiohttp):
    fake_aiohttp(json_data={"response": {"numFound": 0}})

    result = await search_lab_keywords("194495", 2023)

    assert result["keyword_aggregation"] == {}
