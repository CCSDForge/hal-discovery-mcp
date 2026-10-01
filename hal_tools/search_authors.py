from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_authors import search_authors as search_authors_api


@mcp.tool()
async def search_authors(
    query: str,
    rows: Annotated[int, Field(ge=1, le=100)] = 10,
):
    """
    search_authors - Recherche des auteurs dans le référentiel d'auteurs HAL à partir
    de leur nom, prénom ou d'une partie de leur nom.

    UTILISER CET OUTIL lorsque l'utilisateur souhaite identifier un auteur dans HAL
    et récupérer son identifiant HAL (`hal_id`). Cet outil retourne uniquement les
    informations d'identification de l'auteur (nom, identifiant HAL, statut de
    validation).

    NE PAS utiliser cet outil pour rechercher les affiliations, le laboratoire,
    l'université ou le parcours d'un auteur : utiliser `get_author_affiliations`.

    NE PAS utiliser cet outil pour rechercher les publications d'un auteur :
    utiliser `search_author_publications`.

    Parameters:
        query:
            Prénom, nom ou fragment du nom de l'auteur à rechercher
            (ex. : "Yutong Fei").

        rows:
            Nombre maximal d'auteurs à retourner (1 à 100, par défaut : 10).

    Returns:
        num_found:
            Nombre total d'auteurs correspondant à la recherche dans HAL.

        total_returned:
            Nombre d'auteurs effectivement retournés.

        has_more:
            Vaut `True` si `num_found > total_returned`, indiquant que tous les
            résultats n'ont pas été récupérés.

        authors:
            Liste des auteurs trouvés, chaque élément contenant :
            - `name` : nom de l'auteur ;
            - `hal_id` : identifiant HAL ;
            - `docid` : identifiant interne de la forme auteur dans le référentiel ;
            - `validation_status` : statut de validation dans HAL.

            Ces noms de champs ne doivent pas être remplacés par d'autres appellations.

        verification_url:
            Lien cliquable vers l'API HAL listant les auteurs trouvés, à fournir à
            l'utilisateur tel quel pour qu'il puisse vérifier le résultat.

        query_url:
            URL exacte de la requête envoyée à l'API HAL, fournie à des fins de
            traçabilité.

    IMPORTANT - Règles anti-hallucination :
        - Ne rapporter que les informations explicitement présentes dans la liste
          `authors`.
        - Si `num_found` est égal à 0, indiquer explicitement qu'aucun auteur n'a
          été trouvé.
        - Si plusieurs auteurs correspondent à la recherche (homonymes), ne jamais
          en sélectionner un arbitrairement. Présenter tous les résultats ou
          demander à l'utilisateur de préciser l'auteur recherché.
        - Ne jamais inventer un identifiant HAL, un nom ou un statut de validation
          à partir de connaissances externes.
    """
    if not query or not query.strip():
        return {"error": "Le paramètre 'query' est requis et ne peut pas être vide", "query_url": None}

    return await search_authors_api(query.strip(), rows=rows)
