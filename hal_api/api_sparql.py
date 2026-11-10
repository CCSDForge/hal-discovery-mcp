"""
Accès générique au point d'accès SPARQL de HAL : la requête est écrite par
l'agent et transmise après contrôle. Pendant de `api_search.py` (Solr).

Garde-fous : lecture seule (SELECT ou ASK), ni requête fédérée (SERVICE) ni
pragma Virtuoso (DEFINE), seule fonction Virtuoso admise `bif:contains`
(index plein texte), LIMIT borné, pas de pagination (OFFSET).
"""

import re

from hal_api.sparql_client import sparql_get, with_prefixes

MAX_LIMIT = 1000
DEFAULT_LIMIT = 100
MAX_QUERY_CHARS = 5000
# Les textes longs (résumés) saturent le contexte de l'agent : tronqués dans
# la réponse, jamais dans la requête.
MAX_VALUE_CHARS = 1000

# Littéraux, IRI et commentaires sont masqués avant de chercher les mots-clés
# interdits : un titre contenant « delete » ou une IRI contenant « service »
# ne doivent pas faire refuser la requête.
_MASKED = re.compile(
    r'"""(?:[^"\\]|\\.|"(?!""))*"""'
    r"|'''(?:[^'\\]|\\.|'(?!''))*'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r'|<[^<>\s"{}|^`\\]*>'
    r"|#[^\n]*"
)
_FORBIDDEN = re.compile(
    r"\b(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|SERVICE|DEFINE|CONSTRUCT|DESCRIBE)\b",
    re.IGNORECASE,
)
# Appliqué au texte masqué : les IRI des déclarations PREFIX / BASE ont disparu.
_FORM = re.compile(r"^\s*(?:(?:PREFIX\s+[\w-]*:|BASE)\s*)*(SELECT|ASK)\b", re.IGNORECASE)
_VIRTUOSO_FUNCTION = re.compile(r"\b(bif|sql)\s*:\s*(\w+)", re.IGNORECASE)
_LIMIT = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)
_OFFSET = re.compile(r"\bOFFSET\b", re.IGNORECASE)


def mask(query: str) -> str:
    return _MASKED.sub(" ", query)


def validate_query(
    query: str, max_limit: int = MAX_LIMIT, default_limit: int = DEFAULT_LIMIT
) -> tuple[str, int | None]:
    """
    Vérifie la requête et renvoie (requête à exécuter, LIMIT) : LIMIT est ajouté
    s'il est absent ; None pour une requête ASK.
    Lève ValueError avec un message destiné à l'agent pour qu'il la corrige.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("La requête SPARQL est vide")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"Requête trop longue ({len(query)} caractères, max {MAX_QUERY_CHARS})")

    masked = mask(query)
    form = _FORM.match(masked)
    if not form:
        raise ValueError("Seules les requêtes SELECT et ASK sont acceptées (lecture seule)")
    forbidden = sorted({m.upper() for m in _FORBIDDEN.findall(masked)})
    if forbidden:
        raise ValueError(
            f"Mot(s)-clé(s) non autorisé(s) : {forbidden}. Lecture seule (SELECT, ASK), "
            "sans requête fédérée (SERVICE) ni pragma Virtuoso (DEFINE)."
        )
    functions = sorted({f"{p.lower()}:{f}" for p, f in _VIRTUOSO_FUNCTION.findall(masked)} - {"bif:contains"})
    if functions:
        raise ValueError(f"Fonction(s) Virtuoso non autorisée(s) : {functions} (seule bif:contains l'est)")
    if masked.count("{") != masked.count("}"):
        raise ValueError("Accolades déséquilibrées")

    if form.group(1).upper() == "ASK":
        return query.strip(), None

    # Les modificateurs de la requête principale suivent la dernière accolade ;
    # ceux des sous-requêtes, entre accolades, ne sont pas concernés.
    tail = masked[masked.rfind("}") + 1:]
    if _OFFSET.search(tail):
        raise ValueError("OFFSET non autorisé (pas de pagination) : affiner la requête (FILTER, VALUES)")
    limits = _LIMIT.findall(tail)
    if not limits:
        return f"{query.strip()}\nLIMIT {default_limit}", default_limit
    if int(limits[-1]) > max_limit:
        raise ValueError(f"LIMIT doit être au plus {max_limit} (reçu : {limits[-1]})")
    return query.strip(), int(limits[-1])


def _truncate(value):
    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[:MAX_VALUE_CHARS] + " […]"
    return value


def sparql_queries_markdown(query: str, verification: str, count_label: str) -> str:
    """Bloc Markdown prêt à recopier : requête complète et lien qui la rejoue."""
    return "\n".join([
        f"**Requête SPARQL** ({count_label})",
        "```sparql",
        query,
        "```",
        f"[Rejouer sur le SPARQL HAL]({verification})",
    ])


async def sparql(query: str) -> dict:
    """
    Exécute une requête SPARQL de l'agent.

    Returns:
        vars, rows, total_returned, limit_reached, sparql_query, query_url,
        verification_url, sparql_queries ; pour ASK : boolean au lieu de rows ;
        ou {"error", "query_url"} (+ sparql_query si la requête a été envoyée).
    """
    try:
        query, limit = validate_query(query)
        query = with_prefixes(query)
    except ValueError as e:
        return {"error": str(e), "query_url": None}

    result = await sparql_get(query)
    if "error" in result:
        return {**result, "sparql_query": query}

    if limit is None:
        return {
            "boolean": result["boolean"],
            "sparql_query": query,
            "query_url": result["query_url"],
            "verification_url": result["verification_url"],
            "sparql_queries": sparql_queries_markdown(
                query, result["verification_url"], f"réponse : {result['boolean']}"
            ),
        }

    rows = result["rows"]
    return {
        "vars": result["vars"],
        "rows": [{k: _truncate(v) for k, v in r.items()} for r in rows],
        "total_returned": len(rows),
        # LIMIT atteint : il existe probablement d'autres résultats.
        "limit_reached": len(rows) >= limit,
        "sparql_query": query,
        "query_url": result["query_url"],
        "verification_url": result["verification_url"],
        "sparql_queries": sparql_queries_markdown(
            query, result["verification_url"], f"{len(rows)} ligne(s)"
        ),
    }
