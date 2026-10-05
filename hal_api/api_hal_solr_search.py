"""
Accès générique à l'API Solr de HAL : les paramètres sont écrits par l'agent
et transmis tels quels, après contrôle (liste blanche de paramètres, bornes sur
le volume renvoyé). Complète les outils spécialisés pour les questions qu'ils
ne couvrent pas.

Aucune facette, aucun regroupement ni statistique côté Solr (coûteux pour
HAL) : les classements et les comptes par tranche sont calculés par
`hal_api.utils`, à la demande (options `aggregate` et `count_by`).
"""

import re

from hal_api.client import HAL_API_URL, SEARCH_URL, documents_url, hal_get
from hal_api.utils import (
    aggregate_fields,
    check_aggregate_args,
    check_buckets,
    count_buckets,
    readable_url,
)

# Points d'entrée Solr de HAL interrogeables. Chacun a son propre schéma de
# champs (voir la documentation : https://api.archives-ouvertes.fr/docs).
ENDPOINTS = {
    "search": SEARCH_URL,
    "ref/author": f"{HAL_API_URL}/ref/author/",
    "ref/structure": f"{HAL_API_URL}/ref/structure/",
    "ref/anrproject": f"{HAL_API_URL}/ref/anrproject/",
    "ref/europeanproject": f"{HAL_API_URL}/ref/europeanproject/",
    "ref/journal": f"{HAL_API_URL}/ref/journal/",
    "ref/domain": f"{HAL_API_URL}/ref/domain/",
}

# Paramètres Solr acceptés. `wt` est imposé par hal_get ; facet.*, group.*,
# stats.* sont exclus pour ménager HAL, comme `qt`, `shards`, `stream.*`...
ALLOWED_PARAMS = {"q", "fq", "fl", "sort", "start", "rows", "cursorMark", "q.op", "df"}

MAX_ROWS = 100
DEFAULT_ROWS = 10
# Au-delà, la pagination par `start` coûte cher à HAL (2,4 s de calcul Solr
# mesurées à start=10000) : cursorMark donne les mêmes documents à coût constant.
MAX_START = 1000
# fl=* renvoie tous les champs stockés (exports BibTeX, XML...) : environ
# 4 Mo pour 100 documents. Réservé à la découverte des champs.
MAX_ROWS_ALL_FIELDS = 5
# Les champs texte longs (résumés, texte intégral) saturent vite le contexte
# de l'agent : ils sont tronqués dans la réponse, jamais dans la requête.
MAX_FIELD_CHARS = 1000

# Contrôle du contenu, pas seulement des noms de paramètres : HAL accepte les
# paramètres locaux Solr ({!join}, {!frange}...) et les transformateurs de
# documents ([subquery], [child], [explain]), dont le coût n'est pas borné.
LOCAL_PARAMS = "{!"
FIELD_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
FL_PATTERN = re.compile(rf"^\s*(\*|score|{FIELD_NAME})(\s*[,\s]\s*(\*|score|{FIELD_NAME}))*\s*$")
SORT_PATTERN = re.compile(rf"^\s*({FIELD_NAME})\s+(asc|desc)(\s*,\s*({FIELD_NAME})\s+(asc|desc))*\s*$")
DF_PATTERN = re.compile(rf"^{FIELD_NAME}$")


def validate_params(params: dict) -> dict:
    """
    Normalise les paramètres (valeur unique ou liste de chaînes) et vérifie
    qu'ils sont autorisés et bornés. Lève ValueError avec un message destiné à
    l'agent pour qu'il corrige sa requête.
    """
    if not params.get("q"):
        raise ValueError("Le paramètre 'q' est requis (ex. '*:*' pour tous les documents)")

    unknown = sorted(k for k in params if k not in ALLOWED_PARAMS)
    if unknown:
        raise ValueError(
            f"Paramètre(s) non autorisé(s) : {unknown}. Les facettes, regroupements et statistiques "
            "Solr ne sont pas disponibles : utiliser les options 'aggregate' ou 'count_by'."
        )

    normalized = {}
    for key, value in params.items():
        values = value if isinstance(value, list) else [value]
        if not values or not all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in values):
            raise ValueError(f"Valeur invalide pour {key!r} : chaîne, nombre ou liste de chaînes attendue")
        values = [str(v) for v in values]
        normalized[key] = values if isinstance(value, list) else values[0]

    _check_content(normalized)
    _check_int(normalized, "rows", 0, MAX_ROWS)
    _check_int(normalized, "start", 0, MAX_START, hint=" ; pour aller plus loin, paginer avec cursorMark")
    if "*" in re.split(r"[,\s]+", normalized.get("fl", "")) and int(normalized.get("rows", DEFAULT_ROWS)) > MAX_ROWS_ALL_FIELDS:
        raise ValueError(
            f"fl=* n'est accepté qu'avec rows <= {MAX_ROWS_ALL_FIELDS} (pour découvrir les champs) : "
            "lister ensuite les champs utiles dans fl"
        )
    if "start" in normalized and "cursorMark" in normalized:
        raise ValueError("'start' et 'cursorMark' sont incompatibles : utiliser l'un ou l'autre")

    return normalized


def _check_content(params: dict) -> None:
    for key, value in params.items():
        if any(LOCAL_PARAMS in v for v in (value if isinstance(value, list) else [value])):
            raise ValueError(f"Paramètres locaux Solr ({{!...}}) non autorisés dans {key!r}")
    checks = (
        ("fl", FL_PATTERN, "liste de noms de champs séparés par des virgules (ex. 'halId_s,title_s')"),
        ("sort", SORT_PATTERN, "'<champ> asc|desc', séparés par des virgules (ex. 'producedDate_tdate desc')"),
        ("df", DF_PATTERN, "un nom de champ"),
    )
    for key, pattern, expected in checks:
        if key in params and (isinstance(params[key], list) or not pattern.match(params[key])):
            raise ValueError(f"{key!r} invalide : {expected} attendu (reçu : {params[key]!r})")
    if "q.op" in params and params["q.op"] not in ("AND", "OR"):
        raise ValueError("'q.op' doit valoir AND ou OR")


def _check_int(params: dict, key: str, low: int, high: int, hint: str = "") -> None:
    if key not in params:
        return
    value = params[key]
    if isinstance(value, list) or not re.fullmatch(r"-?\d+", value) or not low <= int(value) <= high:
        raise ValueError(f"{key!r} doit être un entier entre {low} et {high} (reçu : {value!r}){hint}")


def _truncate_value(value):
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + " […]"
    if isinstance(value, list):
        return [_truncate_value(v) for v in value]
    return value


async def hal_solr_search(
    endpoint: str,
    params: dict,
    aggregate: list[str] | None = None,
    aggregate_max_docs: int = 300,
    aggregate_top: int = 15,
    count_by: dict[str, str] | None = None,
) -> dict:
    """
    Exécute une requête Solr sur un point d'entrée HAL et, sur demande,
    classe les valeurs de champs (`aggregate`) ou compte par tranche
    (`count_by`) les publications correspondant aux mêmes q / fq.

    Returns:
        dict avec num_found, total_returned, docs, next_cursor_mark,
        aggregations, counts, solr_params, readable_url, query_url,
        verification_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    if endpoint not in ENDPOINTS:
        return {"error": f"endpoint doit valoir l'une de ces valeurs : {list(ENDPOINTS)}", "query_url": None}
    try:
        params = validate_params(params)
        if (aggregate or count_by) and endpoint != "search":
            raise ValueError("'aggregate' et 'count_by' ne s'appliquent qu'au point d'entrée 'search'")
        if aggregate:
            check_aggregate_args(aggregate, aggregate_max_docs, aggregate_top)
        if count_by:
            check_buckets(count_by)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    url = ENDPOINTS[endpoint]
    params.setdefault("rows", str(DEFAULT_ROWS))

    result = await hal_get(url, params)
    if "error" in result:
        return {**result, "solr_params": params}

    data = result["data"]
    response_block = data.get("response", {})
    docs = response_block.get("docs", [])

    output = {
        "num_found": response_block.get("numFound"),
        "total_returned": len(docs),
        "docs": [{k: _truncate_value(v) for k, v in d.items()} for d in docs],
    }
    if data.get("nextCursorMark"):
        output["next_cursor_mark"] = data["nextCursorMark"]

    q = params["q"]
    fq = params.get("fq", [])
    fq = fq if isinstance(fq, list) else [fq]
    if aggregate:
        output["aggregations"] = await aggregate_fields(q, fq, aggregate, aggregate_max_docs, aggregate_top)
    if count_by:
        output["counts"] = await count_buckets(q, fq, count_by)

    output["solr_params"] = params
    output["readable_url"] = readable_url(url, params)
    output["query_url"] = result["query_url"]
    if endpoint == "search":
        # Mêmes publications, triées par pertinence, avec titres et liens HAL.
        output["verification_url"] = documents_url(fq, q=q, sort=None)
    output["solr_queries"] = solr_queries_markdown(output)
    return output


def solr_queries_markdown(output: dict) -> str:
    """
    Bloc Markdown prêt à recopier dans la réponse à l'utilisateur, listant les
    requêtes réellement envoyées à HAL, pour qu'il puisse les vérifier et les
    rejouer. La forme lisible est en bloc de code (elle contient des espaces
    et des guillemets) ; la forme encodée sert de lien cliquable.
    """
    lines = [
        f"**Requête Solr — recherche** (numFound = {output['num_found']})",
        "```",
        output["readable_url"],
        "```",
        f"[Ouvrir dans l'API HAL]({output['query_url']})",
    ]

    aggregations = output.get("aggregations")
    if aggregations and "error" not in aggregations:
        lines += [
            "",
            f"**Requête Solr — classement** ({aggregations['analyzed_docs']} publications analysées"
            f" sur {output['num_found']}, en {aggregations['pages']} page(s) ; comptage fait par le serveur MCP)",
            "```",
            aggregations["readable_url"],
            "```",
        ]

    counts = output.get("counts")
    if counts:
        lines += ["", "**Requêtes Solr — comptes** (même requête avec rows=0 et un fq supplémentaire par tranche)"]
        for label, c in counts.items():
            value = c["num_found"] if "error" not in c else f"erreur : {c['error']}"
            link = f" — [vérifier]({c['query_url']})" if c.get("query_url") else ""
            lines.append(f"- {label} (`fq={c['fq']}`) : {value}{link}")

    return "\n".join(lines)
