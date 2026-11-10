"""
Client HTTP du point d'accès SPARQL de HAL (Virtuoso), pendant de `client.py`
pour l'API Solr.

Même contrat que `hal_get` : ne lève jamais d'exception réseau ni de format ;
renvoie {"vars", "rows", "query_url", "verification_url"} en cas de succès,
{"error", "query_url"} sinon. Les lignes sont simplifiées en {variable: valeur}.
"""

import re

import httpx

from hal_api.client import USER_AGENT

SPARQL_URL = "https://sparql.archives-ouvertes.fr/sparql"
SPARQL_TIMEOUT_SECONDS = 60
# Plafond fixé par le serveur Virtuoso de HAL (ResultSetMaxRows) : au-delà,
# il tronque la réponse sans le signaler.
VIRTUOSO_MAX_ROWS = 10000

# Préfixes du modèle de données HAL, ajoutés à la requête quand elle ne les
# déclare pas elle-même. Attention : les mots-clés sont sous `dc:subject`
# (éléments DC 1.1), pas sous `dcterms:subject`.
PREFIXES = {
    "hal": "http://data.archives-ouvertes.fr/schema/",
    "dcterms": "http://purl.org/dc/terms/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "ore": "http://www.openarchives.org/ore/terms/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "org": "http://www.w3.org/ns/org#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

PREFIX_DECLARATION = re.compile(r"\bPREFIX\s+([A-Za-z][\w-]*)?\s*:", re.IGNORECASE)


def with_prefixes(query: str) -> str:
    """Ajoute en tête les préfixes HAL que la requête ne déclare pas déjà."""
    declared = {p.lower() for p in PREFIX_DECLARATION.findall(query)}
    missing = [f"PREFIX {p}: <{uri}>" for p, uri in PREFIXES.items() if p not in declared]
    return "\n".join(missing + [query.strip()])


def verification_url(query: str) -> str:
    """Lien cliquable qui rejoue la requête et affiche le résultat en tableau HTML."""
    return str(httpx.URL(SPARQL_URL, params={"query": query, "format": "text/html"}))


def _virtuoso_message(text: str) -> str:
    """Première ligne utile d'une erreur Virtuoso (« Virtuoso 37000 Error SP030: ... »)."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:500]
    return "réponse vide"


async def sparql_get(query: str) -> dict:
    """
    Exécute une requête SELECT ou ASK (déjà validée, préfixes compris).

    Returns:
        {"vars": [...], "rows": [{var: valeur}], "boolean": bool | None,
         "query_url", "verification_url"} ou {"error", "query_url"}.
    """
    try:
        async with httpx.AsyncClient(
            timeout=SPARQL_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        ) as client:
            response = await client.get(SPARQL_URL, params={"query": query})
    except httpx.TimeoutException:
        return {
            "error": (
                f"Le point d'accès SPARQL n'a pas répondu dans le délai imparti "
                f"({SPARQL_TIMEOUT_SECONDS} s) : restreindre la requête (VALUES, FILTER, LIMIT)."
            ),
            "query_url": None,
        }
    except httpx.HTTPError as e:
        return {"error": f"Erreur réseau lors de l'appel au SPARQL HAL : {e}", "query_url": None}

    query_url = str(response.url)
    if response.status_code != 200:
        return {
            "error": (
                f"Le SPARQL HAL a répondu avec le code {response.status_code} : "
                f"{_virtuoso_message(response.text)}"
            ),
            "query_url": query_url,
        }
    try:
        data = response.json()
    except ValueError as e:
        return {"error": f"Réponse SPARQL non-JSON : {e}", "query_url": query_url}
    if not isinstance(data, dict):
        return {"error": "Réponse SPARQL inattendue", "query_url": query_url}

    rows = [
        {var: cell.get("value") for var, cell in binding.items()}
        for binding in data.get("results", {}).get("bindings", [])
    ]
    return {
        "vars": data.get("head", {}).get("vars", []),
        "rows": rows,
        "boolean": data.get("boolean"),
        "query_url": query_url,
        "verification_url": verification_url(query),
    }
