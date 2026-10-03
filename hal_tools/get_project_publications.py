from typing import Annotated, Literal

from pydantic import Field

from core.mcp import mcp
from hal_api.api_projects import get_project_publications as _get_project_publications


@mcp.tool()
async def get_project_publications(
    project: str,
    kind: Literal["anr", "europe", "both"] = "both",
    rows: Annotated[int, Field(ge=1, le=50)] = 20,
):
    """
    get_project_publications - Liste les publications HAL financées par un projet ANR ou européen,
    les plus récentes d'abord, et en résume les thématiques (mots-clés, disciplines, laboratoires).

    UTILISER CET OUTIL lorsque l'utilisateur demande, par exemple :
      - "Quelles publications sont issues du projet ANR GrAI ?"
      - "Sur quelles thématiques a travaillé le projet ANR-19-CHIA-0003 ?"
      - "Quels laboratoires participent au projet européen LLMs4EU ?"
    Pour trouver des projets à partir d'un thème : `search_projects`.

    Parameters:
        project: Identifiant HAL du projet (`project_id` renvoyé par search_projects, recommandé),
            référence (ex. "ANR-19-CHIA-0003", "101198470") ou acronyme (ex. "GrAI").
        kind: "anr", "europe" ou "both" (par défaut). Préciser le type évite de mélanger un projet
            ANR et un projet européen de même acronyme.
        rows: Nombre de publications retournées (1 à 50, par défaut : 20).

    Returns:
        num_found / total_returned / has_more: nombre total de publications du projet, nombre
            retourné, et `True` si la liste n'est pas exhaustive.
        matched_projects: projets effectivement désignés par `project` (référence, acronyme,
            titre, programme...). S'il y en a plusieurs (acronyme partagé), le signaler et
            relancer avec `project_id`.
        themes: calculés sur toutes les publications du projet jusqu'à 5000 (sinon les 500 plus
            récentes, avec un `warning`) — `analyzed_docs`, `exhaustive` : keywords ([{keyword, count, verification_url}], en minuscules),
            domains ([{code, label, count}]), labs ([{struct_id, name, count, verification_url}]).
            En cas d'échec du calcul : {"error", "query_url"}.
        publications: hal_id, url, title, authors (10 premiers), num_authors, year, type, venue, doi.
        verification_url: lien listant les publications du projet ; `numFound` = `num_found`.
        query_url: URL exacte de la requête envoyée à l'API HAL.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Décrire les thématiques à partir de `themes` et des titres, en regroupant les variantes
        françaises et anglaises d'un même thème.
      - Seules les publications dont le dépôt déclare le financement sont connues : le préciser.
      - Ne citer que des publications présentes dans `publications`, avec leur lien `url`.
    """
    project = (project or "").strip()
    if not project:
        return {"error": "Le paramètre 'project' est requis et ne peut pas être vide", "query_url": None}

    return await _get_project_publications(project, kind=kind, rows=rows)
