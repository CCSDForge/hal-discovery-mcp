from typing import Annotated

from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.mcp import mcp
from hal_api.network import (
    DEFAULT_MIN_DOCS,
    MAX_MIN_DOCS,
    check_min_docs,
    decode_query,
    fetch_network,
    filter_network,
    vosviewer_json,
)
from hal_api.network import build_network as _build_network
from hal_tools.sparql import SPARQL_DATA_MODEL


BUILD_NETWORK_DOC = (
    """
    build_network - Construit un réseau de co-occurrence à partir d'une requête SPARQL sur HAL
    et renvoie un lien qui l'ouvre dans VOSviewer Online (mise en page et clusters calculés par
    VOSviewer), ainsi qu'un résumé (principaux nœuds et liens).

    UTILISER CET OUTIL quand l'utilisateur veut VOIR des relations : « avec qui publie X ? »,
    « réseau des laboratoires qui travaillent sur la science ouverte », « carte des mots-clés
    associés à tel sujet », « collaborations entre établissements d'un laboratoire »...

    REQUÊTE (`query`) : SELECT qui renvoie des couples (document, élément) :
      ?doc   : le document (regrouper les versions : BIND(COALESCE(?o, ?d) AS ?doc)) ;
      ?item  : l'élément du réseau (IRI de personne / idHAL, de structure, ou mot-clé) ;
      ?label : facultatif, libellé affiché (nom, sigle, mot-clé).
    Deux éléments sont reliés quand ils apparaissent sur un même document ; le poids du lien est
    le nombre de documents communs, la taille d'un nœud son nombre de documents.
    Mêmes garde-fous que l'outil `sparql` ; LIMIT au plus 10 000 (ajouté s'il est absent).
    `min_docs` : ne garder que les éléments présents sur au moins ce nombre de documents
    (défaut 2 ; au plus 1000 éléments, les plus fréquents).
    """ + SPARQL_DATA_MODEL + """
    EXEMPLES DE REQUÊTES :
      Co-autorat d'une personne (idHAL joachim-schopfel), formes auteur regroupées par idHAL :
        SELECT DISTINCT ?doc ?item ?label WHERE {
          ?f ore:isAggregatedBy <https://data.archives-ouvertes.fr/author/joachim-schopfel> .
          ?d dcterms:creator/hal:person ?f .
          OPTIONAL { ?d dcterms:isVersionOf ?o } BIND(COALESCE(?o, ?d) AS ?doc)
          ?d dcterms:creator/hal:person ?p .
          OPTIONAL { ?p ore:isAggregatedBy ?idhal } BIND(COALESCE(?idhal, ?p) AS ?item)
          OPTIONAL { ?p foaf:name ?label }
        }
      Laboratoires co-présents sur les publications « science ouverte » :
        SELECT DISTINCT ?doc ?item ?label WHERE {
          VALUES ?t { "open science"@en "Open science"@en "science ouverte"@fr "Science ouverte"@fr }
          ?d dc:subject ?t .
          OPTIONAL { ?d dcterms:isVersionOf ?o } BIND(COALESCE(?o, ?d) AS ?doc)
          ?d dcterms:creator/hal:structure/org:unitOf* ?item .
          ?item org:classification <https://data.archives-ouvertes.fr/vocabulary/StructureTypeLaboratory> ;
                skos:prefLabel ?nom .
          OPTIONAL { ?item skos:altLabel ?sigle } BIND(COALESCE(?sigle, ?nom) AS ?label)
        }
        (sigle s'il existe, sinon nom complet : les noms complets rendent le graphe illisible)
      Établissements : même requête avec StructureTypeInstitution.
      Mots-clés associés : ?d dc:subject ?item (sans ?label), à partir des mêmes documents.

    Returns:
        num_docs, num_items (éléments trouvés), num_items_kept / num_links_kept (après min_docs),
        top_items (20 éléments les plus fréquents : item, label, docs),
        top_links (20 liens les plus forts : source, target, docs),
        vosviewer_url : lien qui ouvre le réseau dans VOSviewer Online,
        network_json_url : le même réseau au format JSON VOSviewer (téléchargeable),
        sparql_query, verification_url, sparql_queries (comme l'outil `sparql`),
        warnings : réseau tronqué, réduit ou vide — à signaler à l'utilisateur.
        En cas d'erreur : {"error", "query_url"} ; corriger la requête et relancer.

    PRÉSENTATION ET RÈGLES ANTI-HALLUCINATION :
      - Donner le lien `vosviewer_url` (« Ouvrir le réseau dans VOSviewer ») et commenter le
        réseau à partir de top_items et top_links uniquement ; ne pas inventer de nœuds ni de
        liens, ne pas redessiner le graphe.
      - Rappeler les limites : seules les publications déposées dans HAL ; auteur·es sans
        notice absent·es du graphe RDF ; homonymes sans idHAL possibles.
      - Terminer par une section « Requêtes SPARQL utilisées » qui recopie TEL QUEL
        le champ `sparql_queries`.
    """
)


async def build_network(
    query: str,
    min_docs: Annotated[int, Field(ge=1, le=MAX_MIN_DOCS)] = DEFAULT_MIN_DOCS,
):
    return await _build_network(query, min_docs)


build_network.__doc__ = BUILD_NETWORK_DOC
mcp.tool()(build_network)


@mcp.custom_route("/mcp/network.json", methods=["GET"])
async def network_json(request: Request) -> JSONResponse:
    """
    Réseau au format JSON VOSviewer, recalculé à partir de la requête contenue dans l'URL
    (paramètres `q` : requête compressée, `min` : min_docs). Appelé par VOSviewer Online
    depuis le navigateur de l'utilisateur : l'en-tête CORS est indispensable.
    """
    headers = {"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600"}
    try:
        query = decode_query(request.query_params.get("q", ""))
        min_docs = check_min_docs(request.query_params.get("min", DEFAULT_MIN_DOCS))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400, headers=headers)

    fetched = await fetch_network(query)
    if "error" in fetched:
        # Requête refusée avant envoi : 400 ; échec côté SPARQL HAL : 502.
        status = 502 if "sparql_query" in fetched else 400
        return JSONResponse({"error": fetched["error"]}, status_code=status, headers=headers)
    kept, links = filter_network(fetched["network"], min_docs)
    return JSONResponse(vosviewer_json(fetched["network"], kept, links), headers=headers)
