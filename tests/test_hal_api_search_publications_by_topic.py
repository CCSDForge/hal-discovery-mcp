from urllib.parse import parse_qs, urlparse

import pytest

from hal_api.api_search_publications_by_topic import (
    ABSTRACT_MAX_CHARS,
    build_topic_fq,
    search_publications_by_topic,
)

QUERY = '("pratiques informationnelles" OR "information practices") AND (chercheurs OR researchers)'


def test_build_topic_fq_combines_period_types_and_domain():
    fq = build_topic_fq(2020, None, ["ART", "THESE"], "shs.info")

    assert fq == [
        "producedDateY_i:[2020 TO *]",
        "docType_s:(ART OR THESE)",
        'domain_s:"1.shs.info"',
    ]


def test_build_topic_fq_domain_level_follows_depth():
    assert build_topic_fq(None, None, [], "shs") == ['domain_s:"0.shs"']
    assert build_topic_fq(None, None, [], "shs.info.comm") == ['domain_s:"2.shs.info.comm"']


def test_build_topic_fq_without_filters_is_empty():
    assert build_topic_fq(None, None, [], None) == []


@pytest.mark.parametrize("doc_types, domain", [(["ART) OR (*:*"], None), ([], 'shs" OR "x')])
def test_build_topic_fq_rejects_codes_that_could_alter_the_query(doc_types, domain):
    with pytest.raises(ValueError):
        build_topic_fq(None, None, doc_types, domain)


async def test_search_publications_by_topic_parses_docs_and_facets(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {
                "numFound": 90,
                "docs": [
                    {
                        "halId_s": "hal-1",
                        "uri_s": "https://hal.science/hal-1",
                        "title_s": ["Corpus d'enquêtes sur les pratiques d'information des chercheurs"],
                        "authFullName_s": [f"Auteur {i}" for i in range(12)],
                        "producedDateY_i": 2022,
                        "docType_s": "ART",
                        "journalTitle_s": "Revue X",
                        "keyword_s": ["pratiques informationnelles"],
                        "abstract_s": ["mot " * 300],
                        "language_s": ["fr"],
                    },
                    {"halId_s": "hal-2", "title_s": "Chapitre", "docType_s": "COUV", "bookTitle_s": "Ouvrage Y"},
                ],
            },
            "facet_counts": {
                "facet_fields": {
                    "fr_domainAllCodeLabel_fs": ["shs.info_FacetSep_SHS/Sciences de l'information", 59, "shs_FacetSep_SHS", 10],
                    "docType_s": ["ART", 50, "COMM", 40],
                    "producedDateY_i": ["2021", 3, "2022", 7],
                }
            },
        }
    )

    result = await search_publications_by_topic(QUERY, doc_types=["ART", "COUV"], rows=2)

    assert result["num_found"] == 90
    assert result["total_returned"] == 2
    assert result["has_more"] is True

    pub, chapter = result["publications"]
    assert pub["venue"] == "Revue X"
    assert len(pub["authors"]) == 10
    assert pub["num_authors"] == 12
    assert pub["language"] == "fr"
    assert len(pub["abstract"]) <= ABSTRACT_MAX_CHARS + len(" […]")
    assert pub["abstract"].endswith("[…]")
    assert chapter["venue"] == "Ouvrage Y"
    assert chapter["abstract"] is None
    assert chapter["authors"] == []

    assert result["facets"]["by_domain"] == [
        {"code": "shs.info", "label": "SHS/Sciences de l'information", "count": 59},
        {"code": "shs", "label": "SHS", "count": 10},
    ]
    assert result["facets"]["by_doc_type"] == {"ART": 50, "COMM": 40}
    assert result["facets"]["by_year"] == {"2021": 3, "2022": 7}

    params = client.calls[0]["params"]
    assert params["q"] == QUERY
    assert params["fq"] == ["docType_s:(ART OR COUV)"]
    assert "sort" not in params  # pertinence


async def test_search_publications_by_topic_verification_url_keeps_query_filters_and_order(fake_httpx):
    fake_httpx(json_data={"response": {"numFound": 0, "docs": []}})

    relevance = await search_publications_by_topic(QUERY, start_year=2020, doc_types=["ART"])
    by_date = await search_publications_by_topic(QUERY, doc_types=["ART"], sort="date")

    params = parse_qs(urlparse(relevance["verification_url"]).query)
    assert params["q"] == [QUERY]
    assert params["fq"] == ["producedDateY_i:[2020 TO *]", "docType_s:(ART)"]
    assert "sort" not in params
    assert parse_qs(urlparse(by_date["verification_url"]).query)["sort"] == ["producedDate_tdate desc"]


async def test_search_publications_by_topic_returns_error_on_invalid_domain(fake_httpx):
    client = fake_httpx(json_data={})

    result = await search_publications_by_topic(QUERY, domain="SHS INFO")

    assert "domaine" in result["error"]
    assert client.calls == []  # rien n'est envoyé à HAL


async def test_search_publications_by_topic_propagates_rejected_query(fake_httpx):
    fake_httpx(json_data={"error": {"msg": "Error. See help : /docs"}})

    result = await search_publications_by_topic("pratiques (informationnelles")

    assert "rejeté" in result["error"]