from datetime import date
from urllib.parse import parse_qs, urlparse

from hal_api.api_search_author_publications import build_author_query, search_author_publications


def test_build_author_query_prefers_hal_id():
    assert build_author_query("Yutong Fei", "yutong-fei") == 'authIdHal_s:"yutong-fei"'


def test_build_author_query_uses_author_field_not_full_text():
    assert build_author_query('Jean "JD" Dupont', None) == 'authFullName_t:"Jean \\"JD\\" Dupont"'


async def test_search_author_publications_normalizes_title_and_abstract(fake_httpx):
    fake_httpx(
        json_data={
            "response": {
                "numFound": 5,
                "docs": [
                    {
                        "halId_s": "hal-1",
                        "title_s": ["Titre en liste"],
                        "abstract_s": ["Un resume"],
                        "producedDateY_i": 2022,
                        "producedDate_s": "2022-03-01",
                        "docType_s": "ART",
                        "doiId_s": "10.1234/x",
                        "authFullName_s": ["Yutong Fei"],
                    },
                    {
                        "title_s": "Titre simple",
                        "producedDateY_i": 2021,
                        "producedDate_s": "2021-01-01",
                        "docType_s": "COMM",
                    },
                ],
            }
        }
    )

    result = await search_author_publications(hal_id="yutong-fei")

    assert result["num_found"] == 5
    assert result["total_returned"] == 2
    assert result["has_more"] is True
    pubs = result["publications"]
    assert pubs[0]["title"] == "Titre en liste"
    assert pubs[0]["abstract"] == "Un resume"
    assert pubs[0]["authors"] == ["Yutong Fei"]
    assert pubs[0]["doi"] == "10.1234/x"
    assert pubs[0]["doi_url"] == "https://doi.org/10.1234/x"
    assert pubs[1]["title"] == "Titre simple"
    assert pubs[1]["abstract"] is None
    assert pubs[1]["authors"] == []
    assert pubs[1]["doi"] is None
    assert pubs[1]["doi_url"] is None


async def test_search_author_publications_sorts_and_filters_on_full_dates(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    await search_author_publications(
        author_name="Yutong Fei", start_date=date(2020, 3, 1), end_date=date(2022, 6, 30)
    )

    params = client.calls[0]["params"]
    assert params["sort"] == "producedDate_tdate desc"
    assert params["fq"] == "producedDate_tdate:[2020-03-01T00:00:00Z TO 2022-06-30T23:59:59Z]"


async def test_search_author_publications_verification_url_uses_same_filters(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    result = await search_author_publications(hal_id="yutong-fei", start_date=date(2020, 3, 1))

    params = parse_qs(urlparse(result["verification_url"]).query)
    assert params["q"] == ['authIdHal_s:"yutong-fei"']
    assert params["fq"] == ["producedDate_tdate:[2020-03-01T00:00:00Z TO *]"]
    # Lien lisible : pas de résumés, contrairement à la requête de l'outil.
    assert "abstract_s" not in params["fl"][0]


async def test_search_author_publications_without_dates_has_no_filter(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    await search_author_publications(author_name="Yutong Fei")

    assert "fq" not in client.calls[0]["params"]


async def test_search_author_publications_propagates_hal_error(fake_httpx):
    fake_httpx(status_code=500)

    result = await search_author_publications(author_name="Yutong Fei")

    assert "500" in result["error"]