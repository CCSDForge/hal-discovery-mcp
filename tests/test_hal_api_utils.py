import pytest

from collections import Counter
from urllib.parse import parse_qs, urlparse

from hal_api.utils import (
    collect_values,
    count_buckets,
    merge_authors_by_idhal,
    counts_by_value,
    default_sort,
    normalize_keyword,
    rank_authors,
    rank_keywords,
    rank_labs,
    rank_projects,
    readable_value,
)


def page(docs, num_found, cursor):
    return {"json_data": {"response": {"numFound": num_found, "docs": docs}, "nextCursorMark": cursor}}


def test_readable_value_splits_facet_separators():
    assert readable_value("Yolande Maury_FacetSep_yolande-maury") == "Yolande Maury | yolande-maury"
    assert readable_value("A Zeller_FacetSep_") == "A Zeller"
    assert readable_value("L_AlphaSep_93791_FacetSep_GERiiCO") == "93791 | GERiiCO"
    assert readable_value(2024) == "2024"


async def test_collect_values_stops_at_max_docs(fake_httpx):
    client = fake_httpx(responses=[page([{"docType_s": "ART"}] * 100, 5000, f"c{i}") for i in range(5)])

    result = await collect_values("x", [], ["docType_s"], 250, page_size=100)

    assert [c["params"]["rows"] for c in client.calls] == ["100", "100", "50"]
    assert result["exhaustive"] is False


async def test_count_buckets_runs_one_rows0_query_per_bucket(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 7, "docs": []}})

    result = await count_buckets("llm", ["docType_s:ART"], {"2023": "producedDateY_i:2023", "2024": "producedDateY_i:2024"})

    assert all(c["params"]["rows"] == "0" for c in client.calls)
    assert sorted(c["params"]["fq"] for c in client.calls) == [
        ["docType_s:ART", "producedDateY_i:2023"],
        ["docType_s:ART", "producedDateY_i:2024"],
    ]
    assert result["2024"] == {"fq": "producedDateY_i:2024", "num_found": 7, "query_url": "http://example.test/"}


def test_default_sort_uses_recency_without_thematic_query():
    assert default_sort("*:*") == "producedDate_tdate desc,docid asc"
    assert default_sort(' "open science" ') == "score desc,docid asc"


def test_normalize_keyword_merges_case_and_spacing():
    assert normalize_keyword("  Open   Science ") == normalize_keyword("open science") == "open science"


async def test_collect_values_normalizes_per_field_and_counts_docs_with_values(fake_httpx):
    client = fake_httpx(
        json_data={
            "response": {
                "numFound": 3,
                "docs": [
                    {"keyword_s": ["Open Science", "open  science", "LLM"], "docType_s": "ART"},
                    {"keyword_s": [], "docType_s": "ART"},
                    {"docType_s": "COMM"},
                ],
            }
        }
    )

    result = await collect_values(
        "*:*", ["structId_i:1"], ["keyword_s", "docType_s"], 500, page_size=500, normalize={"keyword_s": normalize_keyword}
    )

    params = client.calls[0]["params"]
    assert params["rows"] == "500"
    assert params["sort"] == "producedDate_tdate desc,docid asc"
    # une seule occurrence par document après normalisation
    assert result["counters"]["keyword_s"] == Counter({"open science": 1, "llm": 1})
    assert result["counters"]["docType_s"] == Counter({"ART": 2, "COMM": 1})
    assert result["docs_with_values"] == {"keyword_s": 1, "docType_s": 3}
    assert result["exhaustive"] is True


def test_rank_labs_and_projects_parse_ids_and_build_links():
    labs = rank_labs(Counter({"L_AlphaSep_93791_FacetSep_GERiiCO": 3, "sans-id": 1}), 5, ["docType_s:ART"])

    assert labs[0] == {
        "struct_id": 93791,
        "name": "GERiiCO",
        "count": 3,
        "verification_url": labs[0]["verification_url"],
    }
    assert parse_qs(urlparse(labs[0]["verification_url"]).query)["fq"] == ["docType_s:ART", "labStructId_i:93791"]
    # identifiant inattendu : pas de lien plutôt qu'un filtre invalide
    assert labs[1]["verification_url"] is None

    projects = rank_projects(Counter({"53271_FacetSep_Intelligence Artificielle Verte": 2}), 5, "anrProjectId_i", [])
    assert (projects[0]["project_id"], projects[0]["title"]) == (53271, "Intelligence Artificielle Verte")
    assert parse_qs(urlparse(projects[0]["verification_url"]).query)["fq"] == ["anrProjectId_i:53271"]


def test_rank_authors_escapes_names_in_links():
    (author,) = rank_authors(Counter({'Jean "JD" Dupont_FacetSep_': 1}), 5, [])

    assert author["hal_id"] is None
    assert parse_qs(urlparse(author["verification_url"]).query)["fq"] == ['authFullName_s:"Jean \\"JD\\" Dupont"']


def test_rank_keywords_links_on_analyzed_keyword_field():
    (keyword,) = rank_keywords(Counter({"open science": 4}), 5, ["structId_i:1"])

    assert keyword["count"] == 4
    assert parse_qs(urlparse(keyword["verification_url"]).query)["fq"] == ["structId_i:1", 'keyword_t:"open science"']


def test_counts_by_value_is_sorted():
    assert counts_by_value(Counter({2024: 1, 2021: 3})) == {"2021": 3, "2024": 1}


async def test_collect_values_analyzes_everything_below_complete_ranking_limit(fake_httpx):
    # 1200 résultats : au-delà de max_docs=300, mais sous la limite du classement complet
    client = fake_httpx(
        responses=[page([{"docType_s": "ART"}] * 500, 1200, f"c{i}") for i in range(2)]
        + [page([{"docType_s": "ART"}] * 200, 1200, "c2")]
    )

    result = await collect_values("x", [], ["docType_s"], 300, complete_up_to=5000)

    assert [c["params"]["rows"] for c in client.calls] == ["500", "500", "200"]
    assert result["analyzed_docs"] == 1200
    assert result["exhaustive"] is True


async def test_collect_values_keeps_sample_above_complete_ranking_limit(fake_httpx):
    client = fake_httpx(json_data={"response": {"numFound": 9000, "docs": [{"docType_s": "ART"}] * 500}, "nextCursorMark": "c1"})

    result = await collect_values("x", [], ["docType_s"], 300, complete_up_to=5000)

    # première page pleine pour connaître numFound, mais seules 300 publications comptées
    assert len(client.calls) == 1
    assert result["analyzed_docs"] == 300
    assert result["counters"]["docType_s"]["ART"] == 300
    assert result["exhaustive"] is False


def test_merge_authors_by_idhal_groups_name_forms_but_not_homonyms():
    merged = merge_authors_by_idhal(
        Counter({
            "Cherifa Boukacem_FacetSep_cherifa-boukacem-zeghmouri": 2,
            "Chérifa Boukacem-Zeghmouri_FacetSep_cherifa-boukacem-zeghmouri": 9,
            "Chérifa Boukacem-Zeghmouri_FacetSep_": 1,  # sans idHAL : non rattachée
            "A Zeller_FacetSep_": 3,
        })
    )

    assert merged == Counter({
        "Chérifa Boukacem-Zeghmouri_FacetSep_cherifa-boukacem-zeghmouri": 11,
        "Chérifa Boukacem-Zeghmouri_FacetSep_": 1,
        "A Zeller_FacetSep_": 3,
    })
