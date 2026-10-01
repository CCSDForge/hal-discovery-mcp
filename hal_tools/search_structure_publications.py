from datetime import date
from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_structure_publications import (
    search_structure_publications as _search_structure_publications,
)


@mcp.tool()
async def search_structure_publications(
    struct_ids: Annotated[list[int], Field(min_length=1, max_length=20)],
    start_date: date | None = None,
    end_date: date | None = None,
    doc_types: list[str] | None = None,
    rows: Annotated[int, Field(ge=1, le=50)] = 10,
):
    """
    search_structure_publications - Liste les publications les plus récentes d'une ou de plusieurs
    structures de recherche HAL (laboratoires, universités, réseaux...), de la plus récente à la plus ancienne.

    UTILISER CET OUTIL lorsque l'utilisateur demande les publications d'une structure, par exemple :
      - "Quelles sont les publications les plus récentes des URFIST ?"
      - "Quelles sont les dernières publications de CREATIS ?"
      - "Qu'a publié le laboratoire ELICO en 2024 ?"

    NE PAS utiliser cet outil pour COMPTER les publications d'une structure : utiliser
    `get_publication_statistics_by_structure`, qui donne des chiffres exacts par année et par type.

    Workflow :
      1. Appeler d'abord `search_structures` pour obtenir les identifiants (`id`).
      2. Si la demande porte sur un ensemble de structures (ex. « les URFIST »), passer TOUS les
         identifiants pertinents dans `struct_ids` en un seul appel, quel que soit leur statut
         (VALID, OLD...) : les publications sont fusionnées et triées par date.

    Parameters:
        struct_ids: Identifiants HAL des structures (1 à 20).
        start_date / end_date: Bornes incluses sur la date de production (YYYY-MM-DD), optionnelles.
        doc_types: Codes des types de document à inclure (ex. ["ART", "COMM", "THESE"]).
            Par défaut (None) : tous les types.
        rows: Nombre de publications retournées (1 à 50, par défaut : 10).

    Returns:
        num_found / total_returned / has_more: nombre total de publications des structures
            demandées, nombre retourné, et `True` si la liste n'est pas exhaustive.
        structures: pour chaque structure demandée : id, name, acronym, parent_names,
            validation_status, num_publications, verification_url.
            Plusieurs structures peuvent porter le même `name` : les distinguer par `acronym`
            (ex. « URFIST de Lyon ») et `parent_names`.
            Une publication rattachée à plusieurs structures est comptée pour chacune : la somme
            des `num_publications` peut dépasser `num_found`.
            Une structure OLD est souvent l'ancienne fiche d'une structure encore active : pour un
            comptage par structure, la rapprocher de sa version VALID (même sigle ou même tutelle).
        publications: pour chacune hal_id, url (notice HAL), doi, doi_url (lien https://doi.org/...,
            None si pas de DOI), title, authors (10 premiers), num_authors, date, year, type,
            venue (revue, conférence ou ouvrage), struct_ids (structures demandées auxquelles elle
            est rattachée).
        verification_url: lien cliquable vers l'API HAL listant les mêmes publications dans le même
            ordre ; `numFound` en tête de la réponse est égal à `num_found`.
        query_url: URL exacte de la requête envoyée à l'API HAL.

    Présentation des résultats (OBLIGATOIRE) :
      - Pour CHAQUE publication présentée, toujours afficher :
          * le lien HAL (`url`) ;
          * le DOI sous forme de lien (`doi_url`) lorsqu'il est présent. Si `doi_url` vaut None,
            ne rien afficher pour le DOI : ne jamais en inventer ni en chercher un.
          * la ou les structures concernées, désignées par leur `acronym` (via `struct_ids`).
        Format conseillé :
          Date — Auteurs. Titre. Type. [Structure]
          HAL : <url> — DOI : <doi_url>
      - Recopier les liens tels quels, sans les modifier ni les raccourcir.
      - Toujours fournir aussi le lien `verification_url`.
      - Ne citer que des publications présentes dans `publications`.
    """
    if start_date and end_date and start_date > end_date:
        return {"error": f"start_date ({start_date}) doit être <= end_date ({end_date})", "query_url": None}

    return await _search_structure_publications(
        struct_ids=struct_ids,
        start_date=start_date,
        end_date=end_date,
        doc_types=doc_types,
        rows=rows,
    )
