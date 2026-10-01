from datetime import date

from core.mcp import mcp
from hal_api.api_count_anr_publications import count_anr_publications_logic


@mcp.tool()
async def count_anr_publications(
    struct_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """
    Outil count_anr_publications - Compte les publications HAL financées par des projets ANR, avec leur répartition
    accès ouvert / hors accès ouvert, sans récupérer la liste des publications.

    Utiliser cet outil pour répondre aux questions concernant le volume de publications financées par l'ANR, notamment :
    - "Quel est le nombre de publications financées par l'ANR pour une structure donnée ?"
    - "Combien de publications financées par l'ANR sont en accès ouvert ?"
    - "Quelle est la part des publications financées par l'ANR disponibles en accès ouvert pour une structure donnée ?"

    Si l'utilisateur ne donne que le nom d'une structure, utiliser d'abord `search_structures`
    pour obtenir son identifiant HAL (`id`).

    paramétrage:
        struct_id:
            Identifiant HAL de la structure de recherche (laboratoire, institution,
            université, etc.) pour laquelle les publications ANR doivent être comptées.
            None : toutes structures confondues.

        start_date:
            Date de début incluse de la période d'analyse (date de production), au format YYYY-MM-DD.
            None : aucune borne inférieure.

        end_date:
            Date de fin incluse de la période d'analyse, au format YYYY-MM-DD.
            None : aucune borne supérieure.

    Retours:
        - struct_id, period_applied : rappel des filtres appliqués ;
        - total_anr_publications : nombre total de publications financées par l'ANR ;
        - open_access : dont en accès ouvert ;
        - not_open_access : dont hors accès ouvert ;
        - open_access_rate : part en accès ouvert (entre 0 et 1, None si total nul) ;
        - verification_urls : liens cliquables vers l'API HAL listant les publications
          derrière chaque chiffre (`total`, `open_access`, `not_open_access`). Dans chaque
          lien, `numFound` en tête de la réponse est le nombre exact ; seules les 100 plus
          récentes sont listées ;
        - query_urls : URLs des requêtes de comptage envoyées à l'API HAL, pour traçabilité.

    Présentation des résultats :
      - Toujours fournir à l'utilisateur les liens `verification_urls` des chiffres cités.
      - Recopier les liens tels quels, sans jamais les modifier ni en construire de nouveaux.
    """
    return await count_anr_publications_logic(
        struct_id=struct_id,
        start_date=start_date,
        end_date=end_date,
    )
