from hal_api.client import SEARCH_URL, documents_url, escape_phrase, escape_term, hal_get

FIELDS_TO_FETCH = (
    "docid,producedDateY_i,"
    "structPrimaryHasAuthIdHal_fs,structHasAuthIdHal_fs"
)


def _parse_struct_auth_entry(entry: str):
    """
    Parse une entrée de type structPrimaryHasAuthIdHal_fs / structHasAuthIdHal_fs :
    "{struct_id}_FacetSep_{struct_name}_JoinSep_{hal_id}_FacetSep_{auth_full_name}"

    Retourne None si le format ne correspond pas à ce qui a été observé
    empiriquement (mieux vaut ignorer une entrée mal formée que deviner).
    """
    if not entry or "_JoinSep_" not in entry:
        return None
    left, right = entry.split("_JoinSep_", 1)
    if "_FacetSep_" not in left or "_FacetSep_" not in right:
        return None
    struct_id, struct_name = left.split("_FacetSep_", 1)
    hal_id_found, auth_name = right.split("_FacetSep_", 1)
    return {
        "struct_id": struct_id,
        "struct_name": struct_name,
        "hal_id": hal_id_found,
        "auth_full_name": auth_name,
    }


class _StructureTally:
    """Nombre de publications et première/dernière année par structure."""

    def __init__(self):
        self.entries = {}

    def add(self, struct_id, struct_name, year):
        entry = self.entries.setdefault(struct_id, {
            "struct_id": struct_id,
            "struct_name": struct_name,
            "num_publications": 0,
            "first_year": None,
            "last_year": None,
        })
        entry["num_publications"] += 1
        if year is not None:
            entry["first_year"] = min(year, entry["first_year"] or year)
            entry["last_year"] = max(year, entry["last_year"] or year)

    def by_frequency(self):
        return sorted(self.entries.values(), key=lambda e: e["num_publications"], reverse=True)


def _structure_verification_url(author_query: str, field: str, struct_id: str, id_hal: str) -> str:
    """
    Lien listant les publications où CET auteur est rattaché à CETTE structure
    dans `field`. Le nom de structure et la forme du nom d'auteur varient d'une
    notice à l'autre, d'où les jokers `*` autour de l'id de structure et du hal_id.
    """
    pattern = f"{escape_term(struct_id)}_FacetSep_*_JoinSep_{escape_term(id_hal)}_FacetSep_*"
    return documents_url([f"{field}:{pattern}"], q=author_query)


async def api_get_author_affiliations(id_hal: str, rows: int = 100) -> dict:
    """
    Récupère les affiliations d'un auteur HAL en interrogeant ses publications
    les plus récentes (collection /search/) et en extrayant + agrégeant les
    champs de structure primaire/secondaire, filtrés strictement sur ce hal_id
    exact.

    Args:
        id_hal: identifiant HAL de l'auteur (ex: "yutong-fei")
        rows: nombre max de publications à parcourir pour cet auteur

    Returns:
        dict avec :
          num_found, total_returned, has_more : sur le nombre de PUBLICATIONS
            trouvées pour cet auteur (pas directement le nombre d'affiliations)
          raw_fields_sample : noms de champs réellement présents sur le 1er
            doc (calculé dynamiquement, jamais codé en dur)
          primary_structures_by_frequency : liste de
            {struct_id, struct_name, num_publications, first_year, last_year},
            triée par fréquence décroissante -- calculée UNIQUEMENT à partir de
            structPrimaryHasAuthIdHal_fs, filtrée sur ce hal_id exact.
            C'est la source la plus fiable pour répondre à "quelle est
            l'affiliation principale de cet auteur".
          all_linked_structures_by_frequency : idem mais à partir de
            structHasAuthIdHal_fs -- ensemble plus large, incluant la
            hiérarchie institutionnelle parente. Plus bruité, à ne présenter
            qu'en complément, jamais comme "l'affiliation principale".
          Chaque structure porte aussi un `verification_url` : lien listant les
            publications où l'auteur est rattaché à cette structure.
          verification_url : lien listant toutes les publications de l'auteur.
          query_url : URL exacte appelée, pour traçabilité.

        En cas d'échec, retourne {"error": ..., "query_url": ...}.
    """
    author_query = f'authIdHal_s:"{escape_phrase(id_hal)}"'
    params = {
        "q": author_query,
        "rows": rows,
        "fl": FIELDS_TO_FETCH,
        # Les publications les plus récentes d'abord : si has_more, ce sont
        # les plus anciennes affiliations qui manquent, pas les actuelles.
        "sort": "producedDate_tdate desc",
    }

    result = await hal_get(SEARCH_URL, params)
    if "error" in result:
        return result

    response_block = result["data"].get("response", {})
    docs = response_block.get("docs", [])
    num_found = response_block.get("numFound", len(docs))

    # FIX anti-hallucination : les champs disponibles sont lus dynamiquement
    # depuis la vraie réponse, jamais supposés ou codés en dur.
    raw_fields_sample = list(docs[0].keys()) if docs else []

    primary = _StructureTally()
    all_linked = _StructureTally()

    for doc in docs:
        year = doc.get("producedDateY_i")
        for field, tally in (
            ("structPrimaryHasAuthIdHal_fs", primary),
            ("structHasAuthIdHal_fs", all_linked),
        ):
            seen = set()
            for entry in (doc.get(field) or []):
                parsed = _parse_struct_auth_entry(entry)
                # On ne garde que les entrées qui correspondent EXACTEMENT à ce
                # hal_id -- essentiel si le document a plusieurs co-auteurs.
                # `seen` : une structure ne compte qu'une fois par publication.
                if parsed and parsed["hal_id"] == id_hal and parsed["struct_id"] not in seen:
                    seen.add(parsed["struct_id"])
                    tally.add(parsed["struct_id"], parsed["struct_name"], year)

    structures = {}
    for key, field, tally in (
        ("primary_structures_by_frequency", "structPrimaryHasAuthIdHal_fs", primary),
        ("all_linked_structures_by_frequency", "structHasAuthIdHal_fs", all_linked),
    ):
        structures[key] = [
            {**entry, "verification_url": _structure_verification_url(
                author_query, field, entry["struct_id"], id_hal
            )}
            for entry in tally.by_frequency()
        ]

    return {
        "num_found": num_found,
        "total_returned": len(docs),
        "has_more": num_found > len(docs),
        "raw_fields_sample": raw_fields_sample,
        **structures,
        "verification_url": documents_url(q=author_query),
        "query_url": result["query_url"],
    }