from urllib.parse import parse_qs, urlparse

from hal_api.api_get_publication_statistics_by_structure import search_publication_stats


def pivot_entry(year, types):
    return {
        "field": "producedDateY_i",
        "value": year,
        "count": sum(types.values()),
        "pivot": [{"field": "docType_s", "value": t, "count": c} for t, c in types.items()],
    }


async def test_search_publication_stats_builds_stats_from_pivot_facet(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {"numFound": 6, "docs": []},
            "facet_counts": {
                "facet_pivot": {
                    "producedDateY_i,docType_s": [
                        pivot_entry(2021, {"ART": 1}),
                        pivot_entry(2020, {"ART": 3, "COMM": 2}),
                    ]
                }
            },
        }
    )

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    assert result["num_found"] == 6
    assert result["stats"] == {2020: {"ART": 3, "COMM": 2}, 2021: {"ART": 1}}
    assert list(result["stats"]) == [2020, 2021]
    assert result["query_url"]

    params = client.calls[0]["params"]
    assert params["rows"] == 0
    assert params["facet.pivot"] == "producedDateY_i,docType_s"
    assert params["fq"] == ["structId_i:194495", "producedDateY_i:[2018 TO 2023]"]


async def test_search_publication_stats_builds_verification_urls(fake_httpx):
    fake_httpx(
        json_data={
            "response": {"numFound": 6, "docs": []},
            "facet_counts": {
                "facet_pivot": {
                    "producedDateY_i,docType_s": [
                        pivot_entry(2020, {"ART": 3, "COMM": 2}),
                        pivot_entry(2021, {"ART": 1}),
                    ]
                }
            },
        }
    )

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    urls = result["verification_urls"]
    assert set(urls["by_year"]) == {2020, 2021}
    assert set(urls["by_doc_type"]) == {"ART", "COMM"}

    all_params = parse_qs(urlparse(urls["all"]).query)
    assert all_params["fq"] == ["structId_i:194495", "producedDateY_i:[2018 TO 2023]"]
    # Contrairement à la requête de comptage, le lien liste des publications lisibles.
    assert all_params["rows"] == ["100"]
    assert "title_s" in all_params["fl"][0]
    assert "facet" not in all_params

    year_params = parse_qs(urlparse(urls["by_year"][2021]).query)
    assert year_params["fq"] == ["structId_i:194495", "producedDateY_i:2021"]

    type_params = parse_qs(urlparse(urls["by_doc_type"]["COMM"]).query)
    assert type_params["fq"] == [
        "structId_i:194495",
        "producedDateY_i:[2018 TO 2023]",
        'docType_s:"COMM"',
    ]


async def test_search_publication_stats_without_facets_returns_empty_stats(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    assert result["stats"] == {}
    assert result["verification_urls"]["by_year"] == {}
    assert result["verification_urls"]["all"]


async def test_search_publication_stats_returns_error_on_non_200(fake_httpx):
    fake_httpx(status_code=500)

    result = await search_publication_stats(struct_id=194495, start_year=2018, end_year=2023)

    assert "500" in result["error"]