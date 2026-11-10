"""
Réseaux de co-occurrence construits à partir d'une requête SPARQL de l'agent,
exportés au format VOSviewer (https://app.vosviewer.com).

La requête renvoie des couples (document, élément) — variables ?doc et ?item,
?label facultative. Deux éléments sont liés quand ils apparaissent sur un même
document ; le poids d'un lien est le nombre de documents communs. L'élément
peut être un·e auteur·e (co-autorat), une structure, un mot-clé, etc.

Le lien VOSviewer pointe vers la route HTTP `network.json` du serveur, qui
rejoue la requête à l'ouverture : rien n'est stocké, le lien est reproductible.
"""

import base64
import itertools
import os
import zlib
from collections import Counter, defaultdict
from urllib.parse import urlencode

from hal_api.api_sparql import sparql_queries_markdown, validate_query
from hal_api.sparql_client import VIRTUOSO_MAX_ROWS, sparql_get, with_prefixes

# Adresse publique du serveur MCP (sans « / » final), à surcharger en préproduction.
PUBLIC_URL = os.environ.get("HAL_MCP_PUBLIC_URL", "https://api.archives-ouvertes.fr/mcp").rstrip("/")
NETWORK_ROUTE = "/mcp/network.json"
VOSVIEWER_URL = "https://app.vosviewer.com/"

DEFAULT_MIN_DOCS = 2
MAX_MIN_DOCS = 100
# Au-delà, VOSviewer Online devient lent et le graphe illisible.
MAX_ITEMS = 1000
TOP_SUMMARY = 20


def encode_query(query: str) -> str:
    """Requête compressée pour tenir dans une URL (zlib + base64 URL-safe)."""
    return base64.urlsafe_b64encode(zlib.compress(query.encode(), 9)).decode().rstrip("=")


def decode_query(token: str) -> str:
    """Inverse d'`encode_query`. Lève ValueError si le jeton est invalide."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        # Borne la décompression : une requête valide fait au plus quelques Ko.
        decompressor = zlib.decompressobj()
        data = decompressor.decompress(raw, 100_000)
        if decompressor.unconsumed_tail:
            raise ValueError("requête trop longue")
        return data.decode()
    except (ValueError, zlib.error, UnicodeDecodeError) as e:
        raise ValueError(f"Paramètre q invalide : {e}") from e


def network_json_url(query: str, min_docs: int) -> str:
    return f"{PUBLIC_URL}/network.json?" + urlencode({"q": encode_query(query), "min": min_docs})


def vosviewer_url(query: str, min_docs: int) -> str:
    return f"{VOSVIEWER_URL}?" + urlencode({"json": network_json_url(query, min_docs)})


def check_min_docs(min_docs) -> int:
    try:
        value = int(min_docs)
    except (TypeError, ValueError):
        raise ValueError(f"min_docs doit être un entier (reçu : {min_docs!r})") from None
    if not 1 <= value <= MAX_MIN_DOCS:
        raise ValueError(f"min_docs doit être compris entre 1 et {MAX_MIN_DOCS} (reçu : {value})")
    return value


def cooccurrences(rows: list[dict]) -> dict:
    """Couples (document, élément) → poids des éléments, liens, libellés."""
    items_by_doc = defaultdict(set)
    labels = defaultdict(Counter)
    for row in rows:
        doc, item = row.get("doc"), row.get("item")
        if not doc or not item:
            continue
        items_by_doc[doc].add(item)
        if row.get("label"):
            labels[item][row["label"]] += 1

    weights = Counter(item for items in items_by_doc.values() for item in items)
    links = Counter()
    for items in items_by_doc.values():
        for a, b in itertools.combinations(sorted(items), 2):
            links[(a, b)] += 1
    return {
        "num_docs": len(items_by_doc),
        "weights": weights,
        "links": links,
        "labels": {item: (labels[item].most_common(1)[0][0] if labels[item] else _short(item)) for item in weights},
    }


def _short(item: str) -> str:
    """Libellé par défaut : dernier segment d'une IRI, sinon la valeur elle-même."""
    return item.rstrip("/").rsplit("/", 1)[-1] if item.startswith("http") else item


def filter_network(network: dict, min_docs: int, max_items: int = MAX_ITEMS) -> tuple[list[str], list]:
    """Éléments présents sur au moins `min_docs` documents (les `max_items` premiers), et leurs liens."""
    kept = [item for item, n in network["weights"].most_common(max_items) if n >= min_docs]
    kept_set = set(kept)
    links = [((a, b), n) for (a, b), n in network["links"].most_common() if a in kept_set and b in kept_set]
    return kept, links


def vosviewer_json(network: dict, kept: list[str], links: list) -> dict:
    """Format JSON de VOSviewer : la mise en page et les clusters sont calculés par VOSviewer."""
    index = {item: i + 1 for i, item in enumerate(kept)}
    return {
        "network": {
            "items": [
                {
                    "id": index[item],
                    "label": network["labels"][item],
                    **({"url": item} if item.startswith("http") else {}),
                    "weights": {"Documents": network["weights"][item]},
                }
                for item in kept
            ],
            "links": [
                {"source_id": index[a], "target_id": index[b], "strength": n}
                for (a, b), n in links
            ],
        }
    }


async def fetch_network(query: str) -> dict:
    """
    Valide la requête de l'agent, l'exécute et calcule le réseau.
    Renvoie {"network", "rows", "sparql_query", "verification_url", ...} ou {"error", ...}.
    """
    try:
        checked, limit = validate_query(query, max_limit=VIRTUOSO_MAX_ROWS, default_limit=VIRTUOSO_MAX_ROWS)
    except ValueError as e:
        return {"error": str(e), "query_url": None}
    if limit is None:
        return {"error": "Une requête SELECT renvoyant ?doc et ?item est attendue, pas ASK", "query_url": None}

    full_query = with_prefixes(checked)
    result = await sparql_get(full_query)
    if "error" in result:
        return {**result, "sparql_query": full_query}
    missing = {"doc", "item"} - set(result["vars"])
    if missing:
        return {
            "error": f"La requête doit renvoyer les variables ?doc et ?item (manquantes : {sorted(missing)})",
            "query_url": result["query_url"],
            "sparql_query": full_query,
        }
    return {
        **result,
        "network": cooccurrences(result["rows"]),
        "limit": limit,
        "sparql_query": full_query,
    }


async def build_network(query: str, min_docs: int = DEFAULT_MIN_DOCS) -> dict:
    """
    Construit le réseau et renvoie un résumé pour l'agent et le lien VOSviewer.
    """
    try:
        min_docs = check_min_docs(min_docs)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    fetched = await fetch_network(query)
    if "error" in fetched:
        return fetched

    network = fetched["network"]
    kept, links = filter_network(network, min_docs)
    rows = fetched["rows"]
    labels = network["labels"]

    output = {
        "num_rows": len(rows),
        "num_docs": network["num_docs"],
        "num_items": len(network["weights"]),
        "num_items_kept": len(kept),
        "num_links_kept": len(links),
        "min_docs": min_docs,
        "top_items": [
            {"item": item, "label": labels[item], "docs": network["weights"][item]}
            for item in kept[:TOP_SUMMARY]
        ],
        "top_links": [
            {"source": labels[a], "target": labels[b], "docs": n}
            for (a, b), n in links[:TOP_SUMMARY]
        ],
        "vosviewer_url": vosviewer_url(query, min_docs),
        "network_json_url": network_json_url(query, min_docs),
        "sparql_query": fetched["sparql_query"],
        "verification_url": fetched["verification_url"],
        "sparql_queries": sparql_queries_markdown(
            fetched["sparql_query"], fetched["verification_url"],
            f"{len(rows)} ligne(s), {network['num_docs']} document(s)",
        ),
    }
    warnings = []
    if len(rows) >= fetched["limit"]:
        warnings.append(
            f"Résultat tronqué à {fetched['limit']} lignes : le réseau est incomplet. "
            "Restreindre la requête (période, type de document, structure) avant de l'interpréter."
        )
    if len(network["weights"]) > MAX_ITEMS and len(kept) == MAX_ITEMS:
        warnings.append(f"Seuls les {MAX_ITEMS} éléments les plus fréquents sont conservés.")
    if not kept:
        warnings.append(f"Aucun élément présent sur au moins {min_docs} documents : baisser min_docs.")
    if warnings:
        output["warnings"] = warnings
    return output
