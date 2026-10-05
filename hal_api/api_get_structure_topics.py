"""
Thématiques d'une ou plusieurs structures : mots-clés et disciplines les plus
fréquents sur une période, et, par comparaison avec la période précédente de
même durée, les mots-clés émergents ou en recul.

Sans facette : les publications de chaque période sont parcourues avec un `fl`
réduit (mots-clés, disciplines) et comptées en Python (`hal_api.utils`).
"""

import asyncio

from hal_api.api_search_structures import hal_api_get_structures_by_ids
from hal_api.client import doc_types_fq, documents_url
from hal_api.utils import (
    RECENT_SORT,
    collect_values,
    keyword_url,
    normalize_keyword,
    rank_domains,
    rank_keywords,
)

KEYWORD_FIELD = "keyword_s"
DOMAIN_FIELD = "fr_domainAllCodeLabel_fs"
FIELDS = [KEYWORD_FIELD, DOMAIN_FIELD]

# Publications analysées par période au plus, les plus récentes d'abord ;
# pages larges car seuls deux champs courts sont demandés.
MAX_DOCS_PER_PERIOD = 2000
PAGE_SIZE = 500

TOP_DOMAINS = 10
MAX_DECLINING = 10
# Un mot-clé n'est dit émergent ou en recul qu'à partir de ce nombre de
# publications (dans la période où il est le plus présent), pour ne pas
# monter en épingle un mot-clé isolé.
MIN_COUNT_SMALL = 2
MIN_COUNT = 3
SMALL_PERIOD_DOCS = 100
# Rapport minimal entre les parts des deux périodes.
GROWTH_RATIO = 2


def build_fq(struct_ids: list[int], start_year: int, end_year: int, doc_types: list[str]) -> list[str]:
    """Filtres Solr. Lève ValueError sur un code de type de document invalide."""
    # structId_i inclut la hiérarchie : un établissement couvre ses laboratoires.
    fq = [
        f"structId_i:({' OR '.join(str(int(i)) for i in struct_ids)})",
        f"producedDateY_i:[{int(start_year)} TO {int(end_year)}]",
    ]
    types_fq = doc_types_fq(doc_types)
    if types_fq:
        fq.append(types_fq)
    return fq


async def _period(struct_ids, start_year, end_year, doc_types) -> dict:
    fq = build_fq(struct_ids, start_year, end_year, doc_types)
    collected = await collect_values(
        "*:*",
        fq,
        FIELDS,
        MAX_DOCS_PER_PERIOD,
        sort=RECENT_SORT,
        page_size=PAGE_SIZE,
        normalize={KEYWORD_FIELD: normalize_keyword},
    )
    return {"fq": fq, **collected}


def _period_summary(period: dict, start_year: int, end_year: int) -> dict:
    return {
        "start_year": start_year,
        "end_year": end_year,
        "num_publications": period["num_found"],
        "analyzed_docs": period["analyzed_docs"],
        "exhaustive": period["exhaustive"],
        "docs_with_keywords": period["docs_with_values"][KEYWORD_FIELD],
        "verification_url": documents_url(period["fq"]),
    }


def compare_keywords(recent: dict, reference: dict, top: int) -> dict:
    """
    Compare la part de chaque mot-clé (publications avec ce mot-clé /
    publications ayant des mots-clés) entre les deux périodes.

    Returns:
        {emerging: [...], declining: [...]}, chaque entrée avec keyword,
        recent_count, reference_count, recent_share, reference_share (en %),
        status ("nouveau", "en hausse" ou "en recul"), verification_url
        (période récente pour emerging, période de référence pour declining).
    """
    recent_counter = recent["counters"][KEYWORD_FIELD]
    reference_counter = reference["counters"][KEYWORD_FIELD]
    recent_total = recent["docs_with_values"][KEYWORD_FIELD]
    reference_total = reference["docs_with_values"][KEYWORD_FIELD]
    if not recent_total or not reference_total:
        return {"emerging": [], "declining": []}

    def entry(keyword, status, fq):
        rc, fc = recent_counter[keyword], reference_counter[keyword]
        return {
            "keyword": keyword,
            "recent_count": rc,
            "reference_count": fc,
            "recent_share": round(100 * rc / recent_total, 1),
            "reference_share": round(100 * fc / reference_total, 1),
            "status": status,
            "verification_url": keyword_url(keyword, fq),
        }

    def growth(keyword):
        return recent_counter[keyword] / recent_total - reference_counter[keyword] / reference_total

    min_recent = MIN_COUNT_SMALL if recent_total < SMALL_PERIOD_DOCS else MIN_COUNT
    min_reference = MIN_COUNT_SMALL if reference_total < SMALL_PERIOD_DOCS else MIN_COUNT

    emerging = []
    for keyword, rc in recent_counter.items():
        if rc < min_recent:
            continue
        fc = reference_counter[keyword]
        if fc == 0:
            emerging.append((keyword, "nouveau"))
        elif rc / recent_total >= GROWTH_RATIO * fc / reference_total:
            emerging.append((keyword, "en hausse"))
    emerging.sort(key=lambda item: growth(item[0]), reverse=True)

    declining = [
        keyword
        for keyword, fc in reference_counter.items()
        if fc >= min_reference and recent_counter[keyword] / recent_total <= fc / reference_total / GROWTH_RATIO
    ]
    declining.sort(key=growth)

    return {
        "emerging": [entry(k, status, recent["fq"]) for k, status in emerging[:top]],
        "declining": [entry(k, "en recul", reference["fq"]) for k in declining[:MAX_DECLINING]],
    }


async def get_structure_topics(
    struct_ids: list[int],
    start_year: int,
    end_year: int,
    compare: bool = True,
    doc_types: list[str] | None = None,
    top: int = 20,
) -> dict:
    """
    Mots-clés et disciplines dominants d'une ou plusieurs structures sur
    [start_year, end_year] et, si `compare`, mots-clés émergents ou en recul
    par rapport à la période précédente de même durée.

    Returns:
        dict avec structures, period, main_keywords, main_domains et, si
        `compare`, reference_period, emerging_keywords, declining_keywords
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    struct_ids = list(dict.fromkeys(int(i) for i in struct_ids))
    doc_types = list(doc_types or [])
    length = end_year - start_year + 1
    ref_start, ref_end = start_year - length, start_year - 1
    try:
        build_fq(struct_ids, start_year, end_year, doc_types)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    tasks = [_period(struct_ids, start_year, end_year, doc_types), hal_api_get_structures_by_ids(struct_ids)]
    if compare:
        tasks.append(_period(struct_ids, ref_start, ref_end, doc_types))
    recent, ref, *rest = await asyncio.gather(*tasks)
    if "error" in recent:
        return {"error": recent["error"], "query_url": recent.get("query_url")}

    ref_structures = {} if "error" in ref else ref["structures"]
    response = {
        "structures": [
            {
                "id": i,
                "name": (ref_structures.get(i) or {}).get("name"),
                "acronym": (ref_structures.get(i) or {}).get("acronym"),
                "validation_status": (ref_structures.get(i) or {}).get("validation_status"),
            }
            for i in struct_ids
        ],
        "period": _period_summary(recent, start_year, end_year),
        "main_keywords": rank_keywords(recent["counters"][KEYWORD_FIELD], top, recent["fq"]),
        "main_domains": rank_domains(recent["counters"][DOMAIN_FIELD], TOP_DOMAINS),
        "readable_url": recent["readable_url"],
    }
    if "error" in ref:
        response["structures_warning"] = f"Noms des structures indisponibles : {ref['error']}"

    if compare:
        reference = rest[0]
        if "error" in reference:
            response["comparison_error"] = reference["error"]
        else:
            response["reference_period"] = _period_summary(reference, ref_start, ref_end)
            comparison = compare_keywords(recent, reference, top)
            response["emerging_keywords"] = comparison["emerging"]
            response["declining_keywords"] = comparison["declining"]
    return response
