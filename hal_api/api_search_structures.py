from hal_api.client import REF_STRUCTURE_URL, escape_phrase, hal_get

FIELDS = "docid,label_s,acronym_s,type_s,parentDocid_i,parentName_s,valid_s"


def _to_structure(doc: dict) -> dict:
    return {
        "id": doc.get("docid"),
        "name": doc.get("label_s"),
        "acronym": doc.get("acronym_s"),
        "type": doc.get("type_s"),
        # Multivalués : une structure peut avoir plusieurs tutelles.
        "parent_ids": doc.get("parentDocid_i") or [],
        "parent_names": doc.get("parentName_s") or [],
        "validation_status": doc.get("valid_s"),  # ex: "VALID", "INCOMING", "OLD"
    }


async def hal_api_search_structure(
    structure_name: str,
    rows: int = 10,
) -> dict:
    """
    Interroge l'API HAL /ref/structure pour rechercher une structure par nom ou sigle.

    Args:
        structure_name: nom ou sigle recherché (ex: "Lyon 1", "CNRS", "IP Paris")
        rows: nombre maximum de résultats retournés par HAL

    Returns:
        dict avec:
            - num_found (int): nombre total de structures correspondantes côté HAL
            - structures (list[dict]): structures retournées, détaillées
            - structures_valid / structures_incoming / structures_other_status
            - query_url (str): url exacte appelée (utile pour debug/traçabilité)
    """
    params = {
        "q": f'text:"{escape_phrase(structure_name)}"',
        "fl": FIELDS,
        "rows": rows,
    }
    result = await hal_get(REF_STRUCTURE_URL, params)
    if "error" in result:
        return result

    resp = result["data"].get("response", {})
    docs = resp.get("docs", [])
    num_found = resp.get("numFound", len(docs))

    structures = [_to_structure(doc) for doc in docs]

    return {
        "num_found": num_found,
        "structures": structures,
        "structures_valid": [s for s in structures if s["validation_status"] == "VALID"],
        "structures_incoming": [s for s in structures if s["validation_status"] == "INCOMING"],
        "structures_other_status": [
            s for s in structures
            if s["validation_status"] not in ("VALID", "INCOMING")
        ],
        # La requête liste déjà les structures du référentiel : c'est aussi le lien de vérification.
        "verification_url": result["query_url"],
        "query_url": result["query_url"],
    }


async def hal_api_get_structures_by_ids(struct_ids: list[int]) -> dict:
    """
    Résout plusieurs struct_id en une seule requête au référentiel.

    Returns:
        {"structures": {id (int): structure (voir _to_structure)}, "query_url": str}
        ou {"error": ..., "query_url": ...}. Un id inconnu est simplement absent.
    """
    params = {
        "q": f"docid:({' OR '.join(str(int(i)) for i in struct_ids)})",
        "fl": FIELDS,
        "rows": len(struct_ids),
    }
    result = await hal_get(REF_STRUCTURE_URL, params)
    if "error" in result:
        return result

    docs = result["data"].get("response", {}).get("docs", [])
    return {
        "structures": {int(doc["docid"]): _to_structure(doc) for doc in docs if doc.get("docid")},
        "query_url": result["query_url"],
    }


async def hal_api_get_structure_by_id(struct_id: int) -> dict:
    """
    Interroge l'API HAL /ref/structure pour résoudre un struct_id
    (docid numérique, ex: structId_i sur les publications) vers son nom
    lisible et ses métadonnées. Complément de hal_api_search_structure, qui
    cherche par nom/sigle plutôt que par id exact.

    Args:
        struct_id: identifiant numérique de la structure (docid), ex:
            194495 pour Université Claude Bernard Lyon 1.

    Returns:
        dict avec:
            - found (bool)
            - structure (dict | None): voir _to_structure
            - num_found (int)
            - query_url (str)
    """
    params = {
        "q": f"docid:{int(struct_id)}",
        "fl": FIELDS,
        "rows": 1,
    }
    result = await hal_get(REF_STRUCTURE_URL, params)
    if "error" in result:
        return result

    resp = result["data"].get("response", {})
    docs = resp.get("docs", [])

    return {
        "found": bool(docs),
        "structure": _to_structure(docs[0]) if docs else None,
        "num_found": resp.get("numFound", len(docs)),
        "query_url": result["query_url"],
    }