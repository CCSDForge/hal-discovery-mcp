"""
Projets ANR et européens : recherche par thème (référentiels et publications
financées) et publications d'un projet avec leurs thématiques.

Sans facette : les projets les plus fréquents parmi les publications, et les
thématiques d'un projet, sont comptés en Python (`hal_api.utils`).
"""

import asyncio
import re

from hal_api.client import HAL_API_URL, SEARCH_URL, documents_url, escape_phrase, first, hal_get
from hal_api.utils import (
    RECENT_SORT,
    collect_values,
    normalize_keyword,
    rank_domains,
    rank_keywords,
    rank_labs,
    rank_projects,
)

# Par type de projet : référentiel, champs du référentiel et champs des
# publications. Dans les publications, `<id_field>` vaut le docid du référentiel.
KINDS = {
    "anr": {
        "ref_url": f"{HAL_API_URL}/ref/anrproject/",
        "ref_fields": "docid,title_s,acronym_s,reference_s,acronymProgram_s,callTitle_s,yearDate_s,valid_s",
        "id_field": "anrProjectId_i",
        "title_field": "anrProjectIdTitle_fs",
        "reference_field": "anrProjectReference_s",
        "acronym_field": "anrProjectAcronym_s",
    },
    "europe": {
        "ref_url": f"{HAL_API_URL}/ref/europeanproject/",
        "ref_fields": "docid,title_s,acronym_s,reference_s,financing_s,startDate_s,endDate_s,valid_s",
        "id_field": "europeanProjectId_i",
        "title_field": "europeanProjectIdTitle_fs",
        "reference_field": "europeanProjectReference_s",
        "acronym_field": "europeanProjectAcronym_s",
    },
}

# Programmes ANR structurants (Investissements d'avenir, France 2030) : ils
# financent des établissements ou des réseaux entiers, pas une thématique, et
# dominent les classements par nombre de publications.
STRUCTURING_PROGRAMS = {"IDEX", "ISITE", "I-SITE", "LABX", "EQPX", "EURE", "SFRI", "IHU", "INBS", "IDEFI", "ITE"}

RANKING_DOCS = 300
TOP_PROJECTS = 15
PROJECT_DOCS = 500
TOP_KEYWORDS = 20
TOP_DOMAINS = 10
TOP_LABS = 10
MAX_AUTHORS = 10

PUBLICATION_FIELDS = (
    "halId_s,uri_s,title_s,authFullName_s,producedDateY_i,docType_s,doiId_s,"
    "journalTitle_s,conferenceTitle_s,bookTitle_s"
)
PROJECT_ID_PATTERN = re.compile(r"^\d+$")


def kinds_for(kind: str) -> list[str]:
    return list(KINDS) if kind == "both" else [kind]


def _year_fq(start_year: int | None, end_year: int | None, field: str = "producedDateY_i") -> list[str]:
    if start_year is None and end_year is None:
        return []
    low = int(start_year) if start_year is not None else "*"
    high = int(end_year) if end_year is not None else "*"
    return [f"{field}:[{low} TO {high}]"]


def _to_project(kind: str, doc: dict) -> dict:
    program = doc.get("acronymProgram_s")
    project = {
        "kind": kind,
        "project_id": int(doc["docid"]) if str(doc.get("docid", "")).isdigit() else doc.get("docid"),
        "reference": doc.get("reference_s"),
        "acronym": doc.get("acronym_s"),
        "title": doc.get("title_s"),
        "validation_status": doc.get("valid_s"),
    }
    if kind == "anr":
        project.update({
            "program": program,
            "call": doc.get("callTitle_s"),
            "year": doc.get("yearDate_s"),
            "structuring_program": (program or "").upper() in STRUCTURING_PROGRAMS,
        })
    else:
        project.update({
            "call": doc.get("financing_s"),
            "start_date": (doc.get("startDate_s") or "")[:10] or None,
            "end_date": (doc.get("endDate_s") or "")[:10] or None,
        })
    return project


async def _search_referential(kind: str, query: str, rows: int) -> dict:
    """Projets dont le titre, l'acronyme ou la référence correspondent à `query`."""
    result = await hal_get(KINDS[kind]["ref_url"], {"q": query, "fl": KINDS[kind]["ref_fields"], "rows": rows})
    if "error" in result:
        return result
    response_block = result["data"].get("response", {})
    return {
        "num_found": response_block.get("numFound"),
        "projects": [_to_project(kind, d) for d in response_block.get("docs", [])],
        "query_url": result["query_url"],
    }


async def _referential_by_ids(kind: str, ids: list[int]) -> dict:
    """{project_id: projet} pour compléter les classements (référence, acronyme, programme)."""
    if not ids:
        return {}
    result = await hal_get(
        KINDS[kind]["ref_url"],
        {"q": f"docid:({' OR '.join(str(int(i)) for i in ids)})", "fl": KINDS[kind]["ref_fields"], "rows": len(ids)},
    )
    if "error" in result:
        return {}
    return {p["project_id"]: p for p in (_to_project(kind, d) for d in result["data"].get("response", {}).get("docs", []))}


async def _rank_by_publications(kind: str, query: str, year_fq: list[str]) -> dict:
    """Projets finançant le plus de publications parmi les plus pertinentes sur le thème."""
    spec = KINDS[kind]
    fq = [*year_fq, f"{spec['id_field']}:*"]
    collected = await collect_values(query, fq, [spec["title_field"]], RANKING_DOCS, normalize=str)
    if "error" in collected:
        return {"error": collected["error"], "query_url": collected.get("query_url")}
    ranked = rank_projects(collected["counters"][spec["title_field"]], TOP_PROJECTS, spec["id_field"], fq, q=query, sort=None)
    details = await _referential_by_ids(kind, [p["project_id"] for p in ranked if isinstance(p["project_id"], int)])
    for project in ranked:
        detail = details.get(project["project_id"], {})
        project.update({
            "kind": kind,
            **{k: v for k, v in detail.items() if k not in ("project_id", "title", "kind")},
        })
    return {
        "num_publications": collected["num_found"],
        "analyzed_docs": collected["analyzed_docs"],
        "exhaustive": collected["exhaustive"],
        "projects": ranked,
        "verification_url": documents_url(fq, q=query, sort=None),
    }


async def search_projects(
    query: str,
    kind: str = "both",
    start_year: int | None = None,
    end_year: int | None = None,
    rows: int = 10,
) -> dict:
    """
    Projets liés à un thème, par deux voies complémentaires :
      - by_title : projets dont le titre / l'acronyme correspond (référentiels) ;
      - by_publications : projets qui financent le plus de publications sur le
        thème, parmi les `RANKING_DOCS` plus pertinentes.

    Returns:
        {kind: {by_title, by_publications}} pour chaque type demandé, chaque
        partie pouvant valoir {"error", "query_url"} indépendamment.
    """
    year_fq = _year_fq(start_year, end_year)
    selected = kinds_for(kind)
    results = await asyncio.gather(
        *(_search_referential(k, query, rows) for k in selected),
        *(_rank_by_publications(k, query, year_fq) for k in selected),
    )
    n = len(selected)
    return {
        k: {"by_title": results[i], "by_publications": results[n + i]}
        for i, k in enumerate(selected)
    }


def project_fq(project: str, kind: str) -> str:
    """
    Filtre sur un projet désigné par son identifiant HAL (`project_id`), sa
    référence (ex. ANR-19-CHIA-0003, 101212164) ou son acronyme.
    """
    clauses = []
    for k in kinds_for(kind):
        spec = KINDS[k]
        if PROJECT_ID_PATTERN.match(project):
            clauses.append(f"{spec['id_field']}:{project}")
        clauses.append(f'{spec["reference_field"]}:"{escape_phrase(project)}"')
        clauses.append(f'{spec["acronym_field"]}:"{escape_phrase(project)}"')
    return f"({' OR '.join(clauses)})"


def _to_publication(doc: dict) -> dict:
    authors = doc.get("authFullName_s") or []
    venue = doc.get("journalTitle_s") or doc.get("conferenceTitle_s") or doc.get("bookTitle_s")
    return {
        "hal_id": doc.get("halId_s"),
        "url": doc.get("uri_s"),
        "title": first(doc.get("title_s")),
        "authors": authors[:MAX_AUTHORS],
        "num_authors": len(authors),
        "year": doc.get("producedDateY_i"),
        "type": doc.get("docType_s"),
        "venue": first(venue),
        "doi": doc.get("doiId_s"),
    }


async def get_project_publications(project: str, kind: str = "both", rows: int = 20) -> dict:
    """
    Publications d'un projet (les plus récentes d'abord) et leurs thématiques :
    mots-clés, disciplines et laboratoires les plus fréquents, ainsi que les
    projets réellement désignés (un acronyme peut en désigner plusieurs).

    Returns:
        dict avec num_found, total_returned, has_more, matched_projects,
        themes, publications, verification_url, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    fq = [project_fq(project, kind)]
    selected = kinds_for(kind)
    title_fields = [KINDS[k]["title_field"] for k in selected]
    params = {"q": "*:*", "fq": fq, "fl": PUBLICATION_FIELDS, "rows": rows, "sort": "producedDate_tdate desc"}

    result, collected = await asyncio.gather(
        hal_get(SEARCH_URL, params),
        collect_values(
            "*:*",
            fq,
            ["keyword_s", "fr_domainAllCodeLabel_fs", "labStructIdName_fs", *title_fields],
            PROJECT_DOCS,
            sort=RECENT_SORT,
            normalize={"keyword_s": normalize_keyword},
        ),
    )
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    response = {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
    }
    if "error" in collected:
        response["themes"] = {"error": collected["error"], "query_url": collected.get("query_url")}
    else:
        counters = collected["counters"]
        # Projets financeurs désignés par `project` (filtre) : une publication
        # peut aussi être financée par d'autres projets, à écarter.
        matched = []
        for k in selected:
            spec = KINDS[k]
            ranked = rank_projects(counters[spec["title_field"]], 50, spec["id_field"], [])
            ids = [p["project_id"] for p in ranked if isinstance(p["project_id"], int)]
            details = await _referential_by_ids(k, ids)
            for p in ranked:
                detail = details.get(p["project_id"])
                if detail and project.casefold() in {
                    str(detail.get("project_id")), (detail.get("reference") or "").casefold(), (detail.get("acronym") or "").casefold()
                }:
                    matched.append({**detail, "num_publications_analyzed": p["count"], "verification_url": p["verification_url"]})
        response["matched_projects"] = matched
        response["themes"] = {
            "analyzed_docs": collected["analyzed_docs"],
            "exhaustive": collected["exhaustive"],
            "keywords": rank_keywords(counters["keyword_s"], TOP_KEYWORDS, fq),
            "domains": rank_domains(counters["fr_domainAllCodeLabel_fs"], TOP_DOMAINS),
            "labs": rank_labs(counters["labStructIdName_fs"], TOP_LABS, fq),
        }

    response.update({
        "publications": [_to_publication(d) for d in docs],
        "verification_url": documents_url(fq),
        "query_url": result["query_url"],
    })
    return response
