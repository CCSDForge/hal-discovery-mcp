from typing import Annotated

from pydantic import Field

from core.mcp import mcp
from hal_api.api_search_structures import hal_api_search_structure as _search_structure

MAX_ROWS = 200


@mcp.tool()
async def search_structures(
    structure_name: str,
    rows: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50,
):
    """
    search_structures - Recherche des structures de recherche référencées dans HAL
    (laboratoires, universités, institutions, organismes de recherche, etc.) à
    partir de leur nom ou de leur acronyme.

    UTILISER CET OUTIL lorsque l'utilisateur souhaite :
      - identifier une structure de recherche dans HAL ;
      - récupérer son identifiant HAL (`id`, à passer comme `struct_id` aux
        autres outils) ;
      - retrouver la ou les structures parentes (tutelles) d'un laboratoire ;
      - rechercher une structure à partir d'un nom complet, d'un acronyme ou d'un
        nom partiel (ex. : "Lyon 1", "CNRS", "LIP6").

    L'outil gère les recherches approximatives ou partielles. Par exemple,
    « Lyon 1 » permet de retrouver « Université Claude Bernard Lyon 1 ».

    Les structures sont classées selon leur statut de validation (`validation_status`) :

      - `VALID` :
        Structure officiellement validée dans HAL. Son identifiant peut être utilisé
        comme référence dans les autres outils.

      - `INCOMING` :
        Structure enregistrée mais non encore validée. Son identifiant peut évoluer
        ou être fusionné avec une autre structure.

      - Autres statuts (ex. `OLD`) :
        Structures fermées, fusionnées ou héritées ; à interpréter avec prudence.

    IMPORTANT - Règles anti-hallucination :
      - Ne rapporter que les identifiants, noms et statuts de validation
        explicitement présents dans :
          * `structures_valid`
          * `structures_incoming`
          * `structures_other_status`

      - Ne jamais inventer ou déduire un identifiant HAL à partir de connaissances
        générales, même si la structure est connue.
      - Toujours préciser si un identifiant provient d'une structure `VALID`
        ou `INCOMING`. Ne jamais présenter une structure `INCOMING` comme étant
        officiellement validée.
      - Si `num_found` est égal à 0, indiquer explicitement qu'aucune structure
        correspondante n'a été trouvée.
      - Si `has_more` est égal à `True`, cela signifie que tous les résultats
        n'ont pas été récupérés (`num_found > total_returned`).
        Ne pas conclure qu'une structure est absente ou non validée sur la base
        d'une liste incomplète : préciser la recherche (nom complet, acronyme)
        ou relancer avec un `rows` plus élevé (voir le champ `warning`).

    Parameters:
        structure_name: Nom, acronyme ou fragment du nom de la structure à rechercher (ex. : "Lyon 1", "CNRS", "LIP6").
        rows: Nombre maximal de structures à retourner (1 à 200, par défaut : 50).

    Returns:
        num_found: Nombre total de structures correspondant à la recherche dans HAL.
        total_returned: Nombre de structures effectivement retournées.
        has_more: Vaut `True` si tous les résultats n'ont pas été récupérés (`num_found > total_returned`).
        structures: Liste complète des structures retournées, tous statuts confondus.
            Chaque structure : {id, name, acronym, type, parent_ids, parent_names, validation_status}.
        structures_valid: Sous-ensemble des structures dont le statut est `VALID`.
        structures_incoming: Sous-ensemble des structures dont le statut est `INCOMING`.
        structures_other_status: Sous-ensemble des structures ayant un autre statut de validation.
        verification_url: Lien cliquable vers l'API HAL listant les structures trouvées, à fournir
            à l'utilisateur tel quel pour qu'il puisse vérifier le résultat.
        query_url: URL exacte de la requête envoyée à l'API HAL.
    """
    if not structure_name or not structure_name.strip():
        return {"error": "Le paramètre 'structure_name' est requis et ne peut pas être vide", "query_url": None}

    result = await _search_structure(structure_name=structure_name.strip(), rows=rows)
    if "error" in result:
        return result

    num_found = result["num_found"]
    total_returned = len(result["structures"])
    has_more = num_found > total_returned

    response = {
        "num_found": num_found,
        "total_returned": total_returned,
        "has_more": has_more,
        **{k: v for k, v in result.items() if k != "num_found"},
    }

    if has_more:
        if rows < MAX_ROWS:
            hint = f"Relance cet outil avec un paramètre 'rows' plus élevé (max {MAX_ROWS}) ou une recherche plus précise"
        else:
            hint = "Précise la recherche (nom complet ou acronyme exact)"
        response["warning"] = (
            f"Seuls {total_returned} résultats sur {num_found} ont été récupérés. "
            f"{hint} avant de conclure sur l'absence d'une structure."
        )

    return response
