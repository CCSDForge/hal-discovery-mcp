import aiohttp

from hal_api.api_search_authors import search_authors


async def test_search_authors_returns_parsed_authors(fake_aiohttp):
    fake_aiohttp(
        json_data={
            "response": {
                "numFound": 2,
                "docs": [
                    {
                        "label_s": "Yutong Fei",
                        "idHal_s": "yutong-fei",
                        "docid": 1,
                        "valid_s": "VALID",
                    }
                ],
            }
        }
    )

    result = await search_authors("Yutong Fei", rows=10)

    assert result["num_found"] == 2
    assert result["total_returned"] == 1
    assert result["has_more"] is True
    assert result["authors"] == [
        {"name": "Yutong Fei", "hal_id": "yutong-fei", "docid": 1, "statut_validation": "VALID"}
    ]
    assert result["query_url"]


async def test_search_authors_returns_error_on_non_200(fake_aiohttp):
    fake_aiohttp(status=500)

    result = await search_authors("query")

    assert "500" in result["error"]
    assert result["query_url"]


async def test_search_authors_returns_error_on_invalid_json(fake_aiohttp):
    fake_aiohttp(json_exc=ValueError("bad json"))

    result = await search_authors("query")

    assert "error" in result
    assert result["query_url"]


async def test_search_authors_returns_error_on_network_failure(fake_aiohttp):
    fake_aiohttp(raise_on_enter=aiohttp.ClientError("boom"))

    result = await search_authors("query")

    assert "error" in result
    assert result["query_url"] is None
