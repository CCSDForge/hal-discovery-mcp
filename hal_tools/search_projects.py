from typing import Annotated, Literal

from pydantic import Field

from core.mcp import mcp
from hal_api.api_projects import search_projects as _search_projects


@mcp.tool()
async def search_projects(
    query: str,
    kind: Literal["anr", "europe", "both"] = "both",
    start_year: int | None = None,
    end_year: int | None = None,
    rows: Annotated[int, Field(ge=1, le=50)] = 10,
):
    """
    search_projects - Recherche les projets ANR et européens liés à un thème, à partir des
    référentiels de projets HAL et des publications qu'ils financent.

    UTILISER CET OUTIL lorsque l'utilisateur demande, par exemple :
      - "Quels projets ANR portent sur l'intelligence artificielle en éducation ?"
      - "Quels projets européens financent des recherches sur les LLM ?"
      - "Quel est le projet ANR GrAI ?"
    Pour les publications et les thématiques d'un projet précis : `get_project_publications`.

    CONSTRUCTION DE LA REQUÊTE (`query`, syntaxe Solr) : comme pour search_publications_by_topic,
    synonymes et traduction anglaise entre guillemets reliés par OR, concepts reliés par AND. Un
    acronyme ou une référence de projet (ex. ANR-19-CHIA-0003) fonctionne aussi.

    Parameters:
        query: Requête Solr (thème, acronyme ou référence).
        kind: "anr", "europe" ou "both" (par défaut).
        start_year / end_year: Bornes incluses sur l'année de production des publications
            (classement `by_publications` uniquement).
        rows: Nombre de projets retournés par le référentiel (1 à 50, par défaut : 10).

    Returns:
        Pour chaque type demandé ("anr", "europe") :
          by_title: projets dont le titre, l'acronyme ou la référence correspondent à `query`
              (référentiel HAL) : num_found, projects, query_url.
          by_publications: projets qui financent le plus de publications sur le thème, calculé
              sur toutes ces publications jusqu'à 5000 (`exhaustive: true`), sinon sur les 500 plus
              pertinentes avec un `warning` (affiner alors la requête) : num_publications,
              projects ([{..., count, verification_url}]), verification_url.
          Chaque projet : kind, project_id (identifiant HAL, à passer à get_project_publications),
          reference, acronym, title, validation_status ; ANR : program, call, year,
          structuring_program ; européen : call, start_date, end_date.
          Chaque partie peut valoir {"error", "query_url"} sans invalider l'autre.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Distinguer les deux voies : un projet `by_title` porte explicitement sur le thème ; un projet
        `by_publications` a financé des publications sur ce thème, sans forcément en faire son objet.
      - `structuring_program: true` (IdEx, LabEx, EUR, SFRI...) : programme qui finance un site ou
        un réseau entier, pas une thématique. Le signaler, ou l'écarter d'un classement thématique.
      - HAL ne connaît que les financements déclarés lors du dépôt : ne pas présenter les listes
        comme exhaustives. Ne citer que des projets présents dans la réponse, avec leur référence.
    """
    if not query or not query.strip():
        return {"error": "Le paramètre 'query' est requis et ne peut pas être vide", "query_url": None}
    if start_year is not None and end_year is not None and start_year > end_year:
        return {"error": f"start_year ({start_year}) doit être <= end_year ({end_year})", "query_url": None}

    return await _search_projects(query.strip(), kind=kind, start_year=start_year, end_year=end_year, rows=rows)
