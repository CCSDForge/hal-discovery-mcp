"""
Calculs faits côté serveur MCP à partir de requêtes Solr légères, pour ne pas
utiliser de facettes, regroupements ni statistiques Solr (coûteux pour HAL).

Ces fonctions ne sont pas des outils MCP : `hal_solr_search` les appelle selon
ses options `aggregate` et `count_by`.
"""

import asyncio
import re
from collections import Counter

from hal_api.client import SEARCH_URL, documents_url, escape_phrase, hal_get

# Pages larges : seuls quelques champs courts sont demandés, et chaque
# requête évitée compte davantage pour HAL que la taille de la page.
MAX_ROWS_PER_PAGE = 500

FIELD_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
MAX_AGGREGATE_FIELDS = 8
MAX_AGGREGATE_DOCS = 500
# Jusqu'à ce nombre de résultats, les classements portent sur TOUTES les
# publications (10 pages de 500 au plus, quelques champs courts : environ
# 80 ms de calcul Solr par page). Un échantillon des plus pertinentes peut
# écarter un auteur important dont les titres emploient d'autres termes que
# la requête : au-delà, seul l'échantillon est analysé, avec un avertissement.
COMPLETE_RANKING_LIMIT = 5000
PARTIAL_RANKING_WARNING = (
    "Classement partiel : seules {analyzed} publications sur {num_found} ont été analysées "
    "({order}). Des auteurs, laboratoires ou projets importants peuvent manquer. Affiner la "
    "requête (période, type de document, discipline) pour passer sous {limit} résultats, ce qui "
    "donne un classement complet, plutôt que de présenter ce classement comme représentatif."
)
MAX_TOP = 50
# Tris stables requis par cursorMark (clé unique en dernier). Sans requête
# thématique (q=*:*), tous les scores sont égaux : trier par pertinence
# reviendrait à analyser les publications les plus anciennement déposées.
RELEVANCE_SORT = "score desc,docid asc"
RECENT_SORT = "producedDate_tdate desc,docid asc"

MAX_BUCKETS = 30
# Requêtes de comptage envoyées en parallèle au plus, pour ne pas solliciter
# HAL en rafale.
COUNT_CONCURRENCY = 4


def readable_url(url: str, params: dict) -> str:
    """URL lisible (non encodée), pour montrer la requête à l'utilisateur."""
    parts = []
    for key, value in {**params, "wt": "json"}.items():
        for v in value if isinstance(value, list) else [value]:
            parts.append(f"{key}={v}")
    return f"{url}?{'&'.join(parts)}"


def readable_value(value) -> str:
    """
    Les champs `_fs` contiennent "partie_FacetSep_partie" (ex. nom et idHAL,
    identifiant et nom de structure) et parfois un préfixe "X_AlphaSep_".
    """
    text = str(value).split("_AlphaSep_", 1)[-1]
    return " | ".join(p for p in text.split("_FacetSep_") if p)


def split_facet_value(value) -> list[str]:
    """Parties d'une valeur `_fs` ("12_FacetSep_Nom" -> ["12", "Nom"])."""
    return str(value).split("_AlphaSep_", 1)[-1].split("_FacetSep_")


def default_sort(q: str) -> str:
    """Pertinence pour une requête thématique, date décroissante sinon."""
    return RECENT_SORT if q.strip() in ("*:*", "*") else RELEVANCE_SORT


def normalize_keyword(value: str) -> str:
    """Rapproche les variantes de casse et d'espacement d'un mot-clé."""
    return " ".join(value.split()).casefold()


def check_aggregate_args(fields: list[str], max_docs: int, top: int) -> None:
    """Lève ValueError si les arguments de `aggregate_fields` sont hors bornes."""
    if not fields or len(fields) > MAX_AGGREGATE_FIELDS:
        raise ValueError(f"'aggregate' doit contenir de 1 à {MAX_AGGREGATE_FIELDS} champs")
    invalid = [f for f in fields if not isinstance(f, str) or not FIELD_PATTERN.match(f)]
    if invalid:
        raise ValueError(f"Nom(s) de champ invalide(s) dans 'aggregate' : {invalid}")
    if not 1 <= max_docs <= MAX_AGGREGATE_DOCS:
        raise ValueError(f"'aggregate_max_docs' doit être entre 1 et {MAX_AGGREGATE_DOCS}")
    if not 1 <= top <= MAX_TOP:
        raise ValueError(f"'aggregate_top' doit être entre 1 et {MAX_TOP}")


def check_buckets(buckets: dict) -> None:
    """Lève ValueError si les tranches de `count_buckets` sont invalides."""
    if not buckets or len(buckets) > MAX_BUCKETS:
        raise ValueError(f"'count_by' doit contenir de 1 à {MAX_BUCKETS} tranches")
    if not all(isinstance(f, str) and f.strip() for f in buckets.values()):
        raise ValueError("Chaque tranche de 'count_by' doit être un filtre fq non vide")


async def collect_values(
    q: str,
    fq: list[str],
    fields: list[str],
    max_docs: int,
    sort: str | None = None,
    page_size: int = MAX_ROWS_PER_PAGE,
    normalize=readable_value,
    complete_up_to: int = 0,
) -> dict:
    """
    Récupère jusqu'à `max_docs` publications (pagination cursorMark, seuls
    les champs demandés) et compte en Python les valeurs de chaque champ,
    chaque valeur une fois par document, après `normalize`.

    complete_up_to : si le nombre total de résultats ne le dépasse pas, toutes
        les publications sont analysées, même au-delà de `max_docs`.

    sort : `default_sort(q)` si None.
    normalize : fonction appliquée à chaque valeur, ou {champ: fonction}
        (`str` pour les champs absents du dictionnaire).

    Returns:
        dict avec counters ({champ: Counter}), docs_with_values ({champ:
        nombre de documents ayant au moins une valeur}), analyzed_docs,
        num_found, exhaustive, pages, sort, readable_url
        ou {"error": ..., "query_url": ..., "analyzed_docs": ...} en cas d'échec.
    """
    sort = sort or default_sort(q)
    normalizers = {f: normalize.get(f, str) if isinstance(normalize, dict) else normalize for f in fields}
    counters = {f: Counter() for f in fields}
    docs_with_values = Counter()
    base = {"q": q, "fq": fq, "fl": ",".join(fields), "sort": sort}
    cursor = "*"
    analyzed = 0
    pages = 0
    num_found = 0
    first_page = None
    target = max_docs

    while analyzed < target:
        # Première page : pleine, pour savoir au plus tôt si tout sera analysé.
        rows = page_size if complete_up_to and first_page is None else min(page_size, target - analyzed)
        params = {**base, "rows": str(rows), "cursorMark": cursor}
        result = await hal_get(SEARCH_URL, params)
        if "error" in result:
            return {**result, "analyzed_docs": analyzed}
        pages += 1
        if first_page is None:
            first_page = params

        data = result["data"]
        docs = data.get("response", {}).get("docs", [])
        num_found = data.get("response", {}).get("numFound", 0)
        if pages == 1 and num_found <= complete_up_to:
            target = num_found
        # La première page a pu dépasser `max_docs` : ne compter que la cible.
        docs = docs[: max(target - analyzed, 0)]
        for doc in docs:
            for field in fields:
                value = doc.get(field)
                values = value if isinstance(value, list) else [value] if value is not None else []
                normalized = {normalizers[field](v) for v in values} - {""}
                counters[field].update(normalized)
                docs_with_values[field] += bool(normalized)
        analyzed += len(docs)

        next_cursor = data.get("nextCursorMark")
        if not docs or analyzed >= num_found or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    return {
        "counters": counters,
        "docs_with_values": {f: docs_with_values[f] for f in fields},
        "analyzed_docs": analyzed,
        "num_found": num_found,
        "exhaustive": analyzed >= num_found,
        "pages": pages,
        "sort": sort,
        # Première page ; les suivantes ajoutent le cursorMark renvoyé par HAL.
        "readable_url": readable_url(SEARCH_URL, first_page),
    }


def top_values(counter: Counter, top: int) -> list[dict]:
    return [{"value": v, "count": c} for v, c in counter.most_common(top)]


def partial_warning(collected: dict, limit: int = COMPLETE_RANKING_LIMIT) -> str | None:
    """Avertissement à transmettre à l'agent si le classement n'est pas complet."""
    if collected["exhaustive"]:
        return None
    order = "les plus pertinentes" if collected["sort"] == RELEVANCE_SORT else "les plus récentes"
    return PARTIAL_RANKING_WARNING.format(
        analyzed=collected["analyzed_docs"], num_found=collected["num_found"], order=order, limit=limit
    )


def merge_authors_by_idhal(counter: Counter) -> Counter:
    """
    authFullNameIdHal_fs : regroupe les formes de nom d'un même idHAL (ex.
    avec ou sans accent), sous la forme la plus fréquente. Les formes sans
    idHAL restent séparées : les rattacher à un idHAL d'après le nom seul
    risquerait de confondre des homonymes.
    """
    # Clé de regroupement dans l'ordre de première apparition, pour garder
    # un classement stable à égalité de compte.
    groups: dict[str, Counter] = {}
    for value, count in counter.items():
        _, *rest = split_facet_value(value)
        key = f"idhal:{rest[0]}" if rest and rest[0] else f"value:{value}"
        groups.setdefault(key, Counter())[value] += count
    return Counter({forms.most_common(1)[0][0]: forms.total() for forms in groups.values()})


async def aggregate_fields(
    q: str, fq: list[str], fields: list[str], max_docs: int, top: int, sort: str | None = None
) -> dict:
    """
    Classe les valeurs les plus fréquentes de chaque champ : sur toutes les
    publications jusqu'à `COMPLETE_RANKING_LIMIT` résultats, sinon sur
    `max_docs` publications (voir `collect_values`). Les arguments doivent
    avoir été vérifiés par `check_aggregate_args`.

    Returns:
        dict avec analyzed_docs, num_found, exhaustive, warning (si partiel),
        order, fields ({champ: {distinct_values, top: [{value, count}]}}),
        pages, readable_url
        ou {"error": ..., "query_url": ...} en cas d'échec.
    """
    collected = await collect_values(q, fq, fields, max_docs, sort, normalize=str, complete_up_to=COMPLETE_RANKING_LIMIT)
    if "error" in collected:
        return collected
    counters = dict(collected["counters"])
    if "authFullNameIdHal_fs" in counters:
        counters["authFullNameIdHal_fs"] = merge_authors_by_idhal(counters["authFullNameIdHal_fs"])
    response = {
        "analyzed_docs": collected["analyzed_docs"],
        "num_found": collected["num_found"],
        "exhaustive": collected["exhaustive"],
        # Quelles publications ont été analysées quand la liste n'est pas exhaustive.
        "order": "relevance" if collected["sort"] == RELEVANCE_SORT else "most_recent",
        "fields": {
            field: {
                "distinct_values": len(counter),
                "top": [{"value": readable_value(v), "count": c} for v, c in counter.most_common(top)],
            }
            for field, counter in counters.items()
        },
        "pages": collected["pages"],
        "readable_url": collected["readable_url"],
    }
    warning = partial_warning(collected)
    if warning:
        response["warning"] = warning
    return response


async def count_buckets(q: str, fq: list[str], buckets: dict[str, str]) -> dict:
    """
    Comptes exacts sans facette : une requête `rows=0` par tranche
    (`buckets` : libellé -> filtre fq ajouté à `fq`). Les arguments doivent
    avoir été vérifiés par `check_buckets`.

    Returns:
        {libellé: {fq, num_found, query_url} | {fq, error, query_url}}
    """
    semaphore = asyncio.Semaphore(COUNT_CONCURRENCY)

    async def count(label: str) -> dict:
        async with semaphore:
            result = await hal_get(SEARCH_URL, {"q": q, "fq": fq + [buckets[label]], "rows": "0"})
        if "error" in result:
            return {"fq": buckets[label], **result}
        return {
            "fq": buckets[label],
            "num_found": result["data"].get("response", {}).get("numFound"),
            "query_url": result["query_url"],
        }

    labels = list(buckets)
    results = await asyncio.gather(*(count(label) for label in labels))
    return dict(zip(labels, results))


# Mise en forme des classements calculés par `collect_values` (valeurs brutes,
# `normalize=str`). Chaque entrée porte un lien listant les publications
# correspondantes, sur l'ensemble des résultats : son numFound peut donc
# dépasser `count`, calculé sur les seules publications analysées.


def rank_labs(counter: Counter, top: int, fq: list[str], q: str = "*:*", sort: str | None = None) -> list[dict]:
    """labStructIdName_fs ("id_FacetSep_nom") -> [{struct_id, name, count, verification_url}]"""
    labs = []
    for value, count in counter.most_common(top):
        struct_id, *name = split_facet_value(value)
        labs.append({
            "struct_id": int(struct_id) if struct_id.isdigit() else struct_id,
            "name": name[0] if name else None,
            "count": count,
            "verification_url": documents_url([*fq, f"labStructId_i:{struct_id}"], q=q, sort=sort)
            if struct_id.isdigit() else None,
        })
    return labs


def rank_authors(counter: Counter, top: int, fq: list[str], q: str = "*:*", sort: str | None = None) -> list[dict]:
    """
    authFullNameIdHal_fs ("nom_FacetSep_idhal", idHAL parfois vide) -> [{name, hal_id, count, verification_url}],
    formes de nom d'un même idHAL regroupées (`merge_authors_by_idhal`).
    """
    authors = []
    for value, count in merge_authors_by_idhal(counter).most_common(top):
        name, *rest = split_facet_value(value)
        hal_id = rest[0] if rest and rest[0] else None
        author_fq = f'authIdHal_s:"{escape_phrase(hal_id)}"' if hal_id else f'authFullName_s:"{escape_phrase(name)}"'
        authors.append({
            "name": name,
            "hal_id": hal_id,
            "count": count,
            "verification_url": documents_url([*fq, author_fq], q=q, sort=sort),
        })
    return authors


def rank_domains(counter: Counter, top: int) -> list[dict]:
    """fr_domainAllCodeLabel_fs ("code_FacetSep_libellé") -> [{code, label, count}]"""
    domains = []
    for value, count in counter.most_common(top):
        code, *label = split_facet_value(value)
        domains.append({"code": code, "label": label[0] if label else None, "count": count})
    return domains


def rank_projects(counter: Counter, top: int, id_field: str, fq: list[str], q: str = "*:*", sort: str | None = None) -> list[dict]:
    """anrProjectIdTitle_fs / europeanProjectIdTitle_fs ("id_FacetSep_titre") -> [{project_id, title, count, verification_url}]"""
    projects = []
    for value, count in counter.most_common(top):
        project_id, *title = split_facet_value(value)
        projects.append({
            "project_id": int(project_id) if project_id.isdigit() else project_id,
            "title": title[0] if title else None,
            "count": count,
            "verification_url": documents_url([*fq, f"{id_field}:{project_id}"], q=q, sort=sort)
            if project_id.isdigit() else None,
        })
    return projects


def keyword_url(keyword: str, fq: list[str], q: str = "*:*", sort: str | None = None) -> str:
    """
    Publications dont un mot-clé contient l'expression (champ analysé, donc
    insensible à la casse) : cohérent avec `normalize_keyword`.
    """
    return documents_url([*fq, f'keyword_t:"{escape_phrase(keyword)}"'], q=q, sort=sort)


def counts_by_value(counter: Counter) -> dict:
    """Répartition complète, triée par valeur (années, types de document)."""
    return {str(v): c for v, c in sorted(counter.items(), key=lambda item: str(item[0]))}


def rank_keywords(counter: Counter, top: int, fq: list[str], q: str = "*:*", sort: str | None = None) -> list[dict]:
    """keyword_s normalisés (`normalize_keyword`) -> [{keyword, count, verification_url}]"""
    return [
        {"keyword": keyword, "count": count, "verification_url": keyword_url(keyword, fq, q=q, sort=sort)}
        for keyword, count in counter.most_common(top)
    ]
