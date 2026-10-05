from hal_api.client import REF_AUTHOR_URL, escape_phrase, hal_get


async def search_authors(query: str, rows: int = 10) -> dict:
    """
    Recherche des auteurs dans le référentiel HAL (/ref/author).

    Args:
        query: nom ou fragment de nom de l'auteur.
        rows:  nombre maximum de résultats.

    Returns:
        dict avec num_found, total_returned, has_more, authors, query_url
        ou {"error": ..., "query_url": ...} en cas d'échec.

        Chaque élément de "authors" a la forme :
        {"name": ..., "hal_id": ..., "docid": ..., "validation_status": ...}
    """
    params = {
        "q": f'text:"{escape_phrase(query)}"',
        "fl": "label_s,idHal_s,docid,valid_s",
        "rows": rows,
    }

    result = await hal_get(REF_AUTHOR_URL, params)
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    authors = [
        {
            "name": d.get("label_s"),
            "hal_id": d.get("idHal_s"),
            "docid": d.get("docid"),
            "validation_status": d.get("valid_s"),
        }
        for d in docs
    ]

    return {
        "num_found": num_found,
        "total_returned": len(authors),
        "has_more": num_found > len(authors),
        "authors": authors,
        # La requête liste déjà les formes auteur du référentiel : c'est aussi le lien de vérification.
        "verification_url": result["query_url"],
        "query_url": result["query_url"],
    }
