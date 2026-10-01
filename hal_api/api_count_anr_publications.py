import asyncio
from datetime import date

from hal_api.client import SEARCH_URL, date_range, documents_url, hal_get


def build_anr_fq(
    struct_id: int | None,
    start_date: date | None,
    end_date: date | None,
    open_access: bool | None = None,
) -> list[str]:
    """
    Filtres Solr des publications financées par l'ANR. open_access : True =
    accès ouvert uniquement, False = hors accès ouvert, None = pas de filtre.
    start_date / end_date : bornes incluses sur la date de production (même
    champ que les autres outils).
    """
    fq = ["anrProjectId_i:[* TO *]"]
    if struct_id is not None:
        fq.append(f"structId_i:{int(struct_id)}")
    if open_access is True:
        fq.append("openAccess_bool:true")
    elif open_access is False:
        fq.append("-openAccess_bool:true")
    period_fq = date_range(start_date, end_date, "producedDate_tdate")
    if period_fq:
        fq.append(period_fq)
    return fq


async def count_anr_publications_hal(
    struct_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    open_access: bool | None = None,
) -> dict:
    """
    Compte (rows=0) les publications HAL ayant un financement ANR.
    Voir build_anr_fq pour les filtres.

    Returns:
        {"num_found": int, "query_url": str} ou {"error": ..., "query_url": ...}
    """
    fq = build_anr_fq(struct_id, start_date, end_date, open_access)
    result = await hal_get(SEARCH_URL, {"q": "*:*", "fq": fq, "rows": 0})
    if "error" in result:
        return result

    return {
        "num_found": result["data"].get("response", {}).get("numFound", 0),
        "query_url": result["query_url"],
    }


def build_period_applied(start_date: date | None, end_date: date | None) -> str:
    """
    Construit une chaîne lisible décrivant la période appliquée aux filtres.
    """
    if not start_date and not end_date:
        return "aucune restriction (toutes dates confondues)"
    lower = start_date.isoformat() if start_date else "..."
    upper = end_date.isoformat() if end_date else "..."
    return f"{lower} – {upper}"


async def count_anr_publications_logic(
    struct_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Nombre de publications HAL financées par l'ANR, avec la répartition
    accès ouvert / hors accès ouvert. Les deux comptages sont lancés en
    parallèle ; la part hors accès ouvert est déduite (total - accès ouvert).
    """
    if start_date is not None and end_date is not None and start_date > end_date:
        return {
            "error": f"start_date ({start_date}) doit être <= end_date ({end_date})",
            "query_url": None,
        }

    total, open_access = await asyncio.gather(
        count_anr_publications_hal(struct_id, start_date, end_date),
        count_anr_publications_hal(struct_id, start_date, end_date, open_access=True),
    )
    for result in (total, open_access):
        if "error" in result:
            return result

    total_count = total["num_found"]
    open_count = open_access["num_found"]

    return {
        "struct_id": struct_id,
        "period_applied": build_period_applied(start_date, end_date),
        "total_anr_publications": total_count,
        "open_access": open_count,
        "not_open_access": total_count - open_count,
        "open_access_rate": round(open_count / total_count, 4) if total_count else None,
        "verification_urls": {
            key: documents_url(build_anr_fq(struct_id, start_date, end_date, open_access=oa))
            for key, oa in (("total", None), ("open_access", True), ("not_open_access", False))
        },
        "query_urls": {
            "total": total["query_url"],
            "open_access": open_access["query_url"],
        },
    }
