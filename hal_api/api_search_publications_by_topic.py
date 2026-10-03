import asyncio
import re

from hal_api.client import SEARCH_URL, doc_types_fq, documents_url, first, hal_get
from hal_api.utils import (
    collect_values,
    counts_by_value,
    rank_authors,
    rank_domains,
    rank_labs,
)

# Types retenus par défaut : publications scientifiques (hors mémoires,
# posters, blogs, logiciels...).
DEFAULT_DOC_TYPES = ("ART", "COMM", "THESE", "OUV", "COUV")

ABSTRACT_MAX_CHARS = 600
MAX_AUTHORS = 10
MAX_KEYWORDS = 10

# Classements calculés sans facette, sur les publications les plus
# pertinentes : au-delà, les résultats d'une recherche lexicale sont les plus
# bruités.
RANKING_DOCS = 300
RANKING_FIELDS = ["labStructIdName_fs", "authFullNameIdHal_fs", "fr_domainAllCodeLabel_fs", "producedDateY_i", "docType_s"]
TOP_LABS = 15
TOP_AUTHORS = 15
TOP_DOMAINS = 10

FIELDS = (
    "halId_s,uri_s,title_s,authFullName_s,producedDateY_i,docType_s,doiId_s,"
    "journalTitle_s,conferenceTitle_s,bookTitle_s,keyword_s,abstract_s,language_s"
)

DOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*$")

SORTS = {
    "relevance": None,
    "date": "producedDate_tdate desc",
}


def build_topic_fq(
    start_year: int | None,
    end_year: int | None,
    doc_types: list[str],
    domain: str | None,
) -> list[str]:
    """
    Filtres Solr. Lève ValueError si un code de type ou de domaine n'a pas la
    forme attendue (ils sont insérés tels quels dans la requête).
    """
    fq = []
    if start_year is not None or end_year is not None:
        low = int(start_year) if start_year is not None else "*"
        high = int(end_year) if end_year is not None else "*"
        fq.append(f"producedDateY_i:[{low} TO {high}]")

    types_fq = doc_types_fq(doc_types)
    if types_fq:
        fq.append(types_fq)

    if domain:
        if not DOMAIN_PATTERN.match(domain):
            raise ValueError(f"Code de domaine invalide : {domain!r} (ex. attendus : shs, shs.info)")
        # domain_s indexe chaque niveau préfixé par sa profondeur : "0.shs",
        # "1.shs.info", "2.shs.info.comm". Filtrer ainsi inclut les sous-domaines.
        fq.append(f'domain_s:"{domain.count(".")}.{domain}"')

    return fq


def _truncate(text: str | None, max_chars: int) -> str | None:
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " […]"


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
        "keywords": (doc.get("keyword_s") or [])[:MAX_KEYWORDS],
        "abstract": _truncate(first(doc.get("abstract_s")), ABSTRACT_MAX_CHARS),
        "language": first(doc.get("language_s")),
    }


async def topic_rankings(query: str, fq: list[str]) -> dict:
    """
    Laboratoires, auteurs, disciplines, années et types de document les plus
    fréquents parmi les `RANKING_DOCS` publications les plus pertinentes.
    """
    collected = await collect_values(query, fq, RANKING_FIELDS, RANKING_DOCS, normalize=str)
    if "error" in collected:
        return {"error": collected["error"], "query_url": collected.get("query_url")}
    counters = collected["counters"]
    return {
        "analyzed_docs": collected["analyzed_docs"],
        "exhaustive": collected["exhaustive"],
        "labs": rank_labs(counters["labStructIdName_fs"], TOP_LABS, fq, q=query, sort=None),
        "authors": rank_authors(counters["authFullNameIdHal_fs"], TOP_AUTHORS, fq, q=query, sort=None),
        "domains": rank_domains(counters["fr_domainAllCodeLabel_fs"], TOP_DOMAINS),
        "by_year": counts_by_value(counters["producedDateY_i"]),
        "by_doc_type": counts_by_value(counters["docType_s"]),
    }


async def search_publications_by_topic(
    query: str,
    start_year: int | None = None,
    end_year: int | None = None,
    doc_types: list[str] | None = None,
    domain: str | None = None,
    sort: str = "relevance",
    rows: int = 20,
) -> dict:
    """
    Recherche des publications HAL sur un sujet (titre, résumé, mots-clés...).

    `query` est passée telle quelle à Solr : elle peut contenir des expressions
    entre guillemets et les opérateurs AND / OR / NOT, pour combiner synonymes
    et traductions.

    Returns:
        dict avec num_found, total_returned, has_more, publications, rankings
        (voir `topic_rankings`, ou {"error", "query_url"} si leur calcul échoue),
        verification_url, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    if sort not in SORTS:
        return {"error": f"sort doit valoir l'une de ces valeurs : {list(SORTS)}", "query_url": None}

    try:
        fq = build_topic_fq(start_year, end_year, list(doc_types or []), domain)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    params = {
        "q": query,
        "fq": fq,
        "fl": FIELDS,
        "rows": rows,
    }
    if SORTS[sort]:
        params["sort"] = SORTS[sort]

    result, rankings = await asyncio.gather(hal_get(SEARCH_URL, params), topic_rankings(query, fq))
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    return {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
        "publications": [_to_publication(d) for d in docs],
        "rankings": rankings,
        # Même tri que l'outil : le lien liste les publications dans le même ordre.
        "verification_url": documents_url(fq, q=query, sort=SORTS[sort]),
        "query_url": result["query_url"],
    }
