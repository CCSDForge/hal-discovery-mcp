"""
Client HTTP commun à tous les appels vers l'API HAL.

Centralise : URLs, timeout, User-Agent, contrôle du code HTTP, détection d'une
réponse HTML à la place du JSON, décodage JSON et forme des erreurs. Toutes
les fonctions de hal_api/*.py passent par `hal_get` et renvoient donc les
mêmes clés en cas d'échec : {"error": str, "query_url": str | None}.
"""

import re
from urllib.parse import quote

import httpx

HAL_API_URL = "https://api.archives-ouvertes.fr"
SEARCH_URL = f"{HAL_API_URL}/search/"
REF_AUTHOR_URL = f"{HAL_API_URL}/ref/author/"
REF_STRUCTURE_URL = f"{HAL_API_URL}/ref/structure/"

TIMEOUT_SECONDS = 20
USER_AGENT = "hal-mcp (CCSD)"

# Liens de vérification : champs lisibles par un humain et nombre de
# publications listées par page (le total exact reste dans numFound).
VERIFICATION_FIELDS = "halId_s,uri_s,title_s,producedDate_s,docType_s"
VERIFICATION_ROWS = 100


def escape_phrase(value: str) -> str:
    """
    Échappe une valeur destinée à être placée entre guillemets dans une
    requête Solr (ex: text:"<valeur>"), pour qu'un `"` ou un `\\` saisi par
    l'utilisateur ne casse pas la requête ni n'en modifie la logique.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


SOLR_SPECIAL_CHARS = set('+-&|!(){}[]^"~*?:\\/ ')


def escape_term(value: str) -> str:
    """
    Échappe tous les caractères spéciaux Solr d'une valeur utilisée hors
    guillemets (ex: dans une requête avec jokers `*`, où les guillemets
    désactiveraient les jokers).
    """
    return "".join(f"\\{c}" if c in SOLR_SPECIAL_CHARS else c for c in value)


DOC_TYPE_PATTERN = re.compile(r"^[A-Z]+$")


def doc_types_fq(doc_types: list[str]) -> str | None:
    """
    Filtre Solr sur les types de document (ex: ["ART", "THESE"]), None si la
    liste est vide. Lève ValueError si un code n'a pas la forme attendue : ils
    sont insérés tels quels dans la requête.
    """
    if not doc_types:
        return None
    invalid = [t for t in doc_types if not DOC_TYPE_PATTERN.match(t)]
    if invalid:
        raise ValueError(f"Type(s) de document invalide(s) : {invalid} (ex. attendus : ART, COMM, THESE)")
    return f"docType_s:({' OR '.join(doc_types)})"


def date_range(start, end, field: str) -> str | None:
    """
    Filtre Solr sur un champ date (`*_tdate`) avec bornes incluses, chacune
    optionnelle. `start` / `end` sont des `datetime.date` ou None.
    Renvoie None si aucune borne n'est fournie.
    """
    if start is None and end is None:
        return None
    lower = f"{start.isoformat()}T00:00:00Z" if start else "*"
    upper = f"{end.isoformat()}T23:59:59Z" if end else "*"
    return f"{field}:[{lower} TO {upper}]"


def documents_url(
    fq: list[str] | None = None,
    q: str = "*:*",
    sort: str | None = "producedDate_tdate desc",
) -> str:
    """
    Lien cliquable vers l'API HAL listant les publications qui correspondent
    aux filtres donnés, pour vérifier à la main un chiffre renvoyé par un
    outil : le `numFound` en tête de la réponse est le nombre de publications
    correspondant à ces filtres.

    sort : les plus récentes d'abord par défaut ; None = ordre de pertinence.
    """
    params = {
        "q": q,
        "fq": fq or [],
        "fl": VERIFICATION_FIELDS,
        "rows": VERIFICATION_ROWS,
        "wt": "json",
    }
    if sort:
        params["sort"] = sort
    return str(httpx.URL(SEARCH_URL, params=params))


async def hal_get(url: str, params: dict) -> dict:
    """
    Appelle l'API HAL et renvoie :
      - {"data": <json décodé>, "query_url": str} en cas de succès
      - {"error": str, "query_url": str | None} sinon

    Ne lève jamais d'exception liée au réseau ou au format de la réponse.
    """
    params = {**params, "wt": "json"}
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url, params=params)
    except httpx.TimeoutException:
        return {
            "error": f"L'API HAL n'a pas répondu dans le délai imparti ({TIMEOUT_SECONDS} s)",
            "query_url": None,
        }
    except httpx.HTTPError as e:
        return {"error": f"Erreur réseau lors de l'appel à l'API HAL : {e}", "query_url": None}

    query_url = str(response.url)

    if response.status_code != 200:
        return {
            "error": f"L'API HAL a répondu avec le code {response.status_code}",
            "query_url": query_url,
        }

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" in content_type or response.text.lstrip()[:20].lower().startswith(("<!doctype", "<html")):
        return {
            "error": (
                "L'API HAL a renvoyé du HTML au lieu du JSON attendu. "
                "L'endpoint ou les paramètres sont probablement incorrects."
            ),
            "query_url": query_url,
        }

    try:
        data = response.json()
    except ValueError as e:
        return {"error": f"Réponse HAL non-JSON : {e}", "query_url": query_url}

    # Requête invalide (ex: syntaxe Solr incorrecte) : HAL répond 200 avec
    # {"error": {"msg": ...}} au lieu de résultats. Sans ce contrôle, l'outil
    # annoncerait silencieusement 0 résultat.
    if isinstance(data, dict) and "error" in data:
        detail = data["error"].get("msg") if isinstance(data["error"], dict) else data["error"]
        return {
            "error": (
                f"L'API HAL a rejeté la requête ({detail}). "
                "Vérifier la syntaxe : guillemets et parenthèses équilibrés, opérateurs AND / OR / NOT en majuscules."
            ),
            "query_url": query_url,
        }

    return {"data": data, "query_url": query_url}


def doi_url(doi: str | None) -> str | None:
    """Lien cliquable vers la version éditeur (résolveur doi.org), None sans DOI."""
    if not doi:
        return None
    return f"https://doi.org/{quote(doi.strip(), safe='/')}"


def first(value):
    """HAL renvoie parfois un champ multivalué (liste) là où on attend une valeur."""
    if isinstance(value, list):
        return value[0] if value else None
    return value
