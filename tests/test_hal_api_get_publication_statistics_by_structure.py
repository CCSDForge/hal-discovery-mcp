from hal_api.api_get_publication_statistics_by_structure import search_publication_stats


async def test_search_publication_stats_returns_publications_and_flags(fake_aiohttp):
    fake_aiohttp(
        json_data={
            "response": {
                "numFound": 3,
                "docs": [
                    {"producedDateY_i": 2020, "docType_s": "ART"},
                    {"producedDateY_i": 2021, "docType_s": "COMM"},
                ],
            }
        }
    )

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    assert result["num_found"] == 3
    assert result["total_returned"] == 2
    assert result["has_more"] is True
    assert result["publications"] == [
        {"year": 2020, "type": "ART"},
        {"year": 2021, "type": "COMM"},
    ]
    assert result["query_url"]


async def test_search_publication_stats_returns_error_on_non_200(fake_aiohttp):
    fake_aiohttp(status=500)

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    assert "500" in result["error"]
