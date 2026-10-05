from collections import Counter

import pytest

import hal_api.api_get_structure_topics as module
from hal_api.api_get_structure_topics import build_fq, compare_keywords, get_structure_topics


def period(keywords: dict, docs_with_keywords: int, fq=("structId_i:(1)",)):
    return {
        "fq": list(fq),
        "counters": {"keyword_s": Counter(keywords), "fr_domainAllCodeLabel_fs": Counter()},
        "docs_with_values": {"keyword_s": docs_with_keywords, "fr_domainAllCodeLabel_fs": 0},
    }


def test_build_fq_combines_structures_years_and_types():
    assert build_fq([1, 2], 2023, 2025, ["ART"]) == [
        "structId_i:(1 OR 2)",
        "producedDateY_i:[2023 TO 2025]",
        "docType_s:(ART)",
    ]


def test_build_fq_rejects_invalid_doc_type():
    with pytest.raises(ValueError):
        build_fq([1], 2023, 2025, ["ART OR *:*"])


def test_compare_keywords_finds_new_rising_and_declining_keywords():
    # 50 publications avec mots-clés dans chaque période (< 100 : seuil de 2)
    recent = period({"llm": 8, "open science": 10, "discours": 1, "isolé": 1}, 50)
    reference = period({"open science": 4, "discours": 8, "stable": 3}, 50)

    result = compare_keywords(recent, reference, top=10)

    emerging = {e["keyword"]: e for e in result["emerging"]}
    assert emerging["llm"]["status"] == "nouveau"
    assert emerging["open science"]["status"] == "en hausse"
    assert emerging["open science"]["recent_share"] == 20.0
    assert emerging["open science"]["reference_share"] == 8.0
    # un mot-clé isolé n'est pas une tendance
    assert "isolé" not in emerging
    # tri par progression de la part : llm (+16 points) avant open science (+12 points)
    assert [e["keyword"] for e in result["emerging"]] == ["llm", "open science"]

    assert [d["keyword"] for d in result["declining"]] == ["discours", "stable"]
    assert result["declining"][0]["status"] == "en recul"


def test_compare_keywords_without_reference_keywords_returns_nothing():
    result = compare_keywords(period({"llm": 5}, 10), period({}, 0), top=10)

    assert result == {"emerging": [], "declining": []}


@pytest.fixture
def fake_periods(monkeypatch):
    calls = []

    async def fake_collect(q, fq, fields, max_docs, sort=None, page_size=100, normalize=None, complete_up_to=0):
        calls.append({"q": q, "fq": fq, "max_docs": max_docs, "sort": sort, "page_size": page_size})
        recent = "producedDateY_i:[2023 TO 2025]" in fq
        keywords = {"llm": 5, "open science": 3} if recent else {"open science": 3, "discours": 4}
        return {
            "counters": {
                "keyword_s": Counter(keywords),
                "fr_domainAllCodeLabel_fs": Counter({"shs.info_FacetSep_SHS/Info-com": 7}),
            },
            "docs_with_values": {"keyword_s": 10, "fr_domainAllCodeLabel_fs": 12},
            "analyzed_docs": 12,
            "num_found": 12,
            "exhaustive": True,
            "pages": 1,
            "sort": sort,
            "readable_url": "readable",
        }

    async def fake_ref(struct_ids):
        return {"structures": {70904: {"name": "ELICO", "acronym": "ELICO", "validation_status": "VALID"}}}

    monkeypatch.setattr(module, "collect_values", fake_collect)
    monkeypatch.setattr(module, "hal_api_get_structures_by_ids", fake_ref)
    return calls


async def test_get_structure_topics_compares_with_previous_period_of_same_length(fake_periods):
    result = await get_structure_topics([70904, 70904], 2023, 2025)

    periods = sorted(c["fq"][1] for c in fake_periods)
    assert periods == ["producedDateY_i:[2020 TO 2022]", "producedDateY_i:[2023 TO 2025]"]
    assert all(c["q"] == "*:*" and c["sort"] == "producedDate_tdate desc,docid asc" for c in fake_periods)
    assert all(c["fq"][0] == "structId_i:(70904)" for c in fake_periods)

    assert result["structures"] == [{"id": 70904, "name": "ELICO", "acronym": "ELICO", "validation_status": "VALID"}]
    assert result["period"]["docs_with_keywords"] == 10
    assert result["reference_period"]["start_year"] == 2020
    assert [k["keyword"] for k in result["main_keywords"]] == ["llm", "open science"]
    assert result["main_domains"] == [{"code": "shs.info", "label": "SHS/Info-com", "count": 7}]
    assert [k["keyword"] for k in result["emerging_keywords"]] == ["llm"]
    assert [k["keyword"] for k in result["declining_keywords"]] == ["discours"]


async def test_get_structure_topics_without_comparison_analyzes_one_period(fake_periods):
    result = await get_structure_topics([70904], 2023, 2025, compare=False)

    assert len(fake_periods) == 1
    assert "emerging_keywords" not in result
