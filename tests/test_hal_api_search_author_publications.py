from hal_api.api_search_author_publications import extract_year, search_author_publications


def test_extract_year_returns_none_for_missing_date():
    assert extract_year(None) is None


def test_extract_year_extracts_year_from_iso_date():
    assert extract_year("2023-06-15") == 2023


async def test_search_author_publications_normalizes_title_and_abstract(fake_aiohttp):
    fake_aiohttp(
        json_data={
            "response": {
                "docs": [
                    {
                        "title_s": ["Titre en liste"],
                        "abstract_s": ["Un resume"],
                        "producedDateY_i": 2022,
                        "producedDate_s": "2022-03-01",
                        "docType_s": "ART",
                        "doiId_s": "10.1234/x",
                    },
                    {
                        "title_s": "Titre simple",
                        "producedDateY_i": 2021,
                        "producedDate_s": "2021-01-01",
                        "docType_s": "COMM",
                        "doiId_s": None,
                    },
                ]
            }
        }
    )

    results = await search_author_publications("Yutong Fei")

    assert results[0]["title"] == "Titre en liste"
    assert results[0]["abstract"] == "Un resume"
    assert results[1]["title"] == "Titre simple"
    assert results[1]["abstract"] == "Pas de résumé disponible"


async def test_search_author_publications_builds_date_range_filter(fake_aiohttp):
    session = fake_aiohttp(json_data={"response": {"docs": []}})

    await search_author_publications("Yutong Fei", start_date="2020-01-01", end_date="2022-12-31")

    assert session.calls[0]["params"]["fq"] == "producedDateY_i:[2020 TO 2022]"


async def test_search_author_publications_handles_open_ended_range(fake_aiohttp):
    session = fake_aiohttp(json_data={"response": {"docs": []}})

    await search_author_publications("Yutong Fei", start_date="2020-01-01")

    assert session.calls[0]["params"]["fq"] == "producedDateY_i:[2020 TO *]"
