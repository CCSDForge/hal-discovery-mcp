import asyncio
from datetime import date

from hal_api.api_search_structures import hal_api_get_structures_by_ids
from hal_api.client import SEARCH_URL, date_range, doc_types_fq, documents_url, doi_url, first, hal_get

MAX_AUTHORS = 10

FIELDS = (
    "halId_s,uri_s,title_s,authFullName_s,producedDate_s,producedDateY_i,docType_s,doiId_s,"
    "journalTitle_s,conferenceTitle_s,bookTitle_s,structId_i"
)


def build_structure_fq(
    struct_ids: list[int],
    start_date: date | None,
    end_date: date | None,
    doc_types: list[str],
) -> list[str]:
    """Filtres Solr. Lève ValueError sur un code de type de document invalide."""
    # structId_i contient la structure de rattachement ET toute sa hiérarchie :
    # filtrer sur un établissement inclut donc les publications de ses laboratoires.
    fq = [f"structId_i:({' OR '.join(str(int(i)) for i in struct_ids)})"]
    period_fq = date_range(start_date, end_date, "producedDate_tdate")
    if period_fq:
        fq.append(period_fq)
    types_fq = doc_types_fq(doc_types)
    if types_fq:
        fq.append(types_fq)
    return fq


def _to_publication(doc: dict, requested_ids: set[int]) -> dict:
    authors = doc.get("authFullName_s") or []
    venue = doc.get("journalTitle_s") or doc.get("conferenceTitle_s") or doc.get("bookTitle_s")
    return {
        "hal_id": doc.get("halId_s"),
        "url": doc.get("uri_s"),
        "doi": doc.get("doiId_s"),
        "doi_url": doi_url(doc.get("doiId_s")),
        "title": first(doc.get("title_s")),
        "authors": authors[:MAX_AUTHORS],
        "num_authors": len(authors),
        "date": doc.get("producedDate_s"),
        "year": doc.get("producedDateY_i"),
        "type": doc.get("docType_s"),
        "venue": first(venue),
        # Parmi les structures demandées, celles auxquelles la publication est rattachée.
        "struct_ids": sorted(requested_ids & set(doc.get("structId_i") or [])),
    }


async def search_structure_publications(
    struct_ids: list[int],
    start_date: date | None = None,
    end_date: date | None = None,
    doc_types: list[str] | None = None,
    rows: int = 10,
) -> dict:
    """
    Publications les plus récentes d'une ou plusieurs structures HAL.

    Deux requêtes en parallèle : les publications (avec un comptage par
    structure via facet.query) et la résolution des structures dans le
    référentiel (nom, sigle, tutelles), indispensable quand plusieurs
    structures portent le même nom (ex: les URFIST).

    Returns:
        dict avec num_found, total_returned, has_more, structures,
        publications, verification_url, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    struct_ids = list(dict.fromkeys(int(i) for i in struct_ids))
    try:
        fq = build_structure_fq(struct_ids, start_date, end_date, list(doc_types or []))
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    sort = "producedDate_tdate desc"
    params = {
        "q": "*:*",
        "fq": fq,
        "fl": FIELDS,
        "rows": rows,
        "sort": sort,
        "facet": "true",
        "facet.query": [f"structId_i:{i}" for i in struct_ids],
    }

    result, ref = await asyncio.gather(
        hal_get(SEARCH_URL, params),
        hal_api_get_structures_by_ids(struct_ids),
    )
    if "error" in result:
        return result
    # Le référentiel ne sert qu'à nommer les structures : son échec n'empêche
    # pas de renvoyer les publications.
    ref_structures = {} if "error" in ref else ref["structures"]

    data = result["data"]
    response_block = data.get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))
    facet_queries = data.get("facet_counts", {}).get("facet_queries", {})

    other_fq = fq[1:]
    structures = []
    for struct_id in struct_ids:
        ref_entry = ref_structures.get(struct_id) or {}
        structures.append({
            "id": struct_id,
            "name": ref_entry.get("name"),
            "acronym": ref_entry.get("acronym"),
            "parent_names": ref_entry.get("parent_names", []),
            "validation_status": ref_entry.get("validation_status"),
            "num_publications": facet_queries.get(f"structId_i:{struct_id}", 0),
            "verification_url": documents_url([f"structId_i:{struct_id}", *other_fq], sort=sort),
        })

    requested = set(struct_ids)
    response = {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
        "structures": structures,
        "publications": [_to_publication(d, requested) for d in docs],
        "verification_url": documents_url(fq, sort=sort),
        "query_url": result["query_url"],
    }
    if "error" in ref:
        response["structures_warning"] = f"Noms des structures indisponibles : {ref['error']}"
    return response
