from hal_api.api_search_authors import search_authors


async def test_search_authors_returns_parsed_authors(fake_httpx):
    fake_httpx(
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
        {"name": "Yutong Fei", "hal_id": "yutong-fei", "docid": 1, "validation_status": "VALID"}
    ]
    assert result["query_url"]
    assert result["verification_url"] == result["query_url"]


async def test_search_authors_escapes_quotes_in_query(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    await search_authors('Jean "JD" Dupont')

    assert client.calls[0]["params"]["q"] == 'text:"Jean \\"JD\\" Dupont"'


async def test_search_authors_propagates_hal_error(fake_httpx):
    fake_httpx(status_code=500)

    result = await search_authors("query")

    assert "500" in result["error"]
    assert result["query_url"]
