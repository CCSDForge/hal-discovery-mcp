"""
Accès générique à l'API Solr de HAL : les paramètres sont écrits par l'agent
et transmis tels quels, après contrôle (liste blanche de paramètres, bornes sur
le volume renvoyé). Complète les outils spécialisés pour les questions qu'ils
ne couvrent pas.

Recherche seule, sans calcul : aucune facette, aucun regroupement ni
statistique (coûteux pour HAL), pas de pagination (`start`, `cursorMark`).
"""

import re

from hal_api.client import HAL_API_URL, SEARCH_URL, documents_url, hal_get
from hal_api.utils import readable_url

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
# Pas de pagination (`start`, `cursorMark`) : l'agent affine sa requête.
ALLOWED_PARAMS = {"q", "fq", "fl", "sort", "rows", "q.op", "df"}

MAX_ROWS = 100
DEFAULT_ROWS = 10
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
            f"Paramètre(s) non autorisé(s) : {unknown}. Ni pagination (start, cursorMark) ni "
            "facettes, regroupements ou statistiques Solr : affiner q / fq."
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
    if "*" in re.split(r"[,\s]+", normalized.get("fl", "")) and int(normalized.get("rows", DEFAULT_ROWS)) > MAX_ROWS_ALL_FIELDS:
        raise ValueError(
            f"fl=* n'est accepté qu'avec rows <= {MAX_ROWS_ALL_FIELDS} (pour découvrir les champs) : "
            "lister ensuite les champs utiles dans fl"
        )
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


def _check_int(params: dict, key: str, low: int, high: int) -> None:
    if key not in params:
        return
    value = params[key]
    if isinstance(value, list) or not re.fullmatch(r"-?\d+", value) or not low <= int(value) <= high:
        raise ValueError(f"{key!r} doit être un entier entre {low} et {high} (reçu : {value!r})")


def _truncate_value(value):
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + " […]"
    if isinstance(value, list):
        return [_truncate_value(v) for v in value]
    return value


async def search(endpoint: str, params: dict) -> dict:
    """
    Exécute une requête Solr sur un point d'entrée HAL.

    Returns:
        dict avec num_found, total_returned, docs, solr_params,
        readable_url, query_url, verification_url, solr_queries
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    if endpoint not in ENDPOINTS:
        return {"error": f"endpoint doit valoir l'une de ces valeurs : {list(ENDPOINTS)}", "query_url": None}
    try:
        params = validate_params(params)
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

    q = params["q"]
    fq = params.get("fq", [])
    fq = fq if isinstance(fq, list) else [fq]
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
    Bloc Markdown prêt à recopier dans la réponse à l'utilisateur, avec la
    requête réellement envoyée à HAL, pour qu'il puisse la vérifier et la
    rejouer. La forme lisible est en bloc de code (elle contient des espaces
    et des guillemets) ; la forme encodée sert de lien cliquable.
    """
    return "\n".join([
        f"**Requête Solr — recherche** (numFound = {output['num_found']})",
        "```",
        output["readable_url"],
        "```",
        f"[Ouvrir dans l'API HAL]({output['query_url']})",
    ])
