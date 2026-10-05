from collections import Counter
from urllib.parse import parse_qs, urlparse

import hal_api.api_projects as module
from hal_api.api_projects import _to_project, get_project_publications, project_fq, search_projects

ANR_REF_DOC = {
    "docid": "53271",
    "title_s": "Intelligence Artificielle Verte",
    "acronym_s": "GrAI",
    "reference_s": "ANR-19-CHIA-0003",
    "acronymProgram_s": "Programme national pour l'Intelligence Artificielle",
    "yearDate_s": "2019",
    "valid_s": "VALID",
}
IDEX_REF_DOC = {"docid": "37796", "acronym_s": "UNISTRA", "reference_s": "ANR-10-IDEX-0002", "acronymProgram_s": "IDEX"}


def test_project_fq_matches_id_reference_or_acronym():
    assert project_fq("GrAI", "anr") == '(anrProjectReference_s:"GrAI" OR anrProjectAcronym_s:"GrAI")'
    assert project_fq("53271", "anr").startswith("(anrProjectId_i:53271 OR ")
    both = project_fq("LLMs4EU", "both")
    assert "anrProjectAcronym_s" in both and "europeanProjectAcronym_s" in both


def test_project_fq_escapes_quotes():
    assert '\\"' in project_fq('A" OR *:* OR "B', "anr")


def test_to_project_flags_structuring_anr_programs():
    assert _to_project("anr", IDEX_REF_DOC)["structuring_program"] is True
    grai = _to_project("anr", ANR_REF_DOC)
    assert grai["structuring_program"] is False
    assert (grai["project_id"], grai["reference"], grai["year"]) == (53271, "ANR-19-CHIA-0003", "2019")

    eu = _to_project("europe", {"docid": "1", "startDate_s": "2025-09-01T00:00:00Z", "financing_s": "ERC-2024-COG"})
    assert (eu["start_date"], eu["call"]) == ("2025-09-01", "ERC-2024-COG")


async def test_search_projects_combines_referential_and_funded_publications(monkeypatch):
    calls = []

    async def fake_hal_get(url, params):
        calls.append({"url": url, "params": params})
        if params["q"].startswith("docid:"):
            return {"data": {"response": {"docs": [ANR_REF_DOC, IDEX_REF_DOC]}}, "query_url": "ids"}
        return {"data": {"response": {"numFound": 1, "docs": [ANR_REF_DOC]}}, "query_url": "ref"}

    async def fake_collect(q, fq, fields, max_docs, sort=None, page_size=100, normalize=None, complete_up_to=0):
        calls.append({"collect": fq, "fields": fields, "complete_up_to": complete_up_to})
        return {
            "sort": "score desc,docid asc",
            "counters": {fields[0]: Counter({"37796_FacetSep_UNISTRA": 9, "53271_FacetSep_Intelligence Artificielle Verte": 4})},
            "docs_with_values": {},
            "analyzed_docs": 13,
            "num_found": 40,
            "exhaustive": False,
        }

    monkeypatch.setattr(module, "hal_get", fake_hal_get)
    monkeypatch.setattr(module, "collect_values", fake_collect)

    result = await search_projects('"intelligence artificielle"', kind="anr", start_year=2022)

    assert list(result) == ["anr"]
    assert result["anr"]["by_title"]["projects"][0]["acronym"] == "GrAI"
    ranked = result["anr"]["by_publications"]
    assert ranked["exhaustive"] is False
    assert [(p["acronym"], p["count"], p["structuring_program"]) for p in ranked["projects"]] == [
        ("UNISTRA", 9, True),
        ("GrAI", 4, False),
    ]
    assert "Classement partiel" in ranked["warning"]
    collect = next(c for c in calls if "collect" in c)
    assert collect["complete_up_to"] == 5000
    assert collect["collect"] == ["producedDateY_i:[2022 TO *]", "anrProjectId_i:*"]
    assert collect["fields"] == ["anrProjectIdTitle_fs"]


async def test_get_project_publications_keeps_only_designated_projects(monkeypatch):
    async def fake_hal_get(url, params):
        if params["q"].startswith("docid:"):
            return {"data": {"response": {"docs": [ANR_REF_DOC, IDEX_REF_DOC]}}, "query_url": "ids"}
        return {
            "data": {"response": {"numFound": 6, "docs": [{"halId_s": "hal-1", "title_s": ["Spiking"], "authFullName_s": ["A"]}]}},
            "query_url": "search",
        }

    async def fake_collect(q, fq, fields, max_docs, sort=None, page_size=100, normalize=None, complete_up_to=0):
        counters = {f: Counter() for f in fields}
        counters["keyword_s"] = Counter({"neuromorphic": 3})
        # les publications de GrAI sont aussi financées par l'IdEx : ce n'est pas le projet demandé
        counters["anrProjectIdTitle_fs"] = Counter({"53271_FacetSep_Intelligence Artificielle Verte": 6, "37796_FacetSep_UNISTRA": 2})
        return {"counters": counters, "docs_with_values": {}, "analyzed_docs": 6, "num_found": 6, "exhaustive": True}

    monkeypatch.setattr(module, "hal_get", fake_hal_get)
    monkeypatch.setattr(module, "collect_values", fake_collect)

    result = await get_project_publications("grai", kind="anr")

    assert result["num_found"] == 6
    assert [p["acronym"] for p in result["matched_projects"]] == ["GrAI"]
    assert result["themes"]["keywords"][0]["keyword"] == "neuromorphic"
    assert result["publications"][0]["title"] == "Spiking"
    fq = parse_qs(urlparse(result["verification_url"]).query)["fq"]
    assert fq == ['(anrProjectReference_s:"grai" OR anrProjectAcronym_s:"grai")']
