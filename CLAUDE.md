# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Autonomie

Projet existant/porté par le CCSD pour HAL (voir `CLAUDE.md` utilisateur) → **autonomie faible** :
valider les choix structurants (ajout d'un nouvel outil MCP, changement de format de retour,
changement de dépendance HTTP, etc.) avant d'agir.

## What this is

An MCP (Model Context Protocol) server exposing tools to query the HAL open-archive APIs
(`api.archives-ouvertes.fr`) — authors, structures, publications, ANR-funded publications,
keyword statistics. Built on `mcp.server.mcpserver.MCPServer` (the `mcp` PyPI package, v2.x —
this class was called `FastMCP`, at `mcp.server.fastmcp.FastMCP`, in the 1.x line; see
`DECISIONS.md`), served over `streamable-http`. See `README.md` for the functional description of
each tool (in French) and example prompts — keep it in sync when tools change.

Production/preprod endpoints: `https://api.archives-ouvertes.fr/mcp` and
`https://api-preprod.archives-ouvertes.fr/mcp`.

## Running

There is no linter config in this repo yet.

### Tests

```bash
make test   # bootstraps a local venv/ (gitignored) and runs pytest
```

pytest + pytest-asyncio (`asyncio_mode = auto` in `pytest.ini`, so `async def test_...` needs no
marker). `tests/conftest.py` provides `fake_aiohttp`/`fake_httpx` fixtures that monkeypatch
`aiohttp.ClientSession`/`httpx.AsyncClient` with an in-memory fake session/client — no real HTTP
calls, no extra HTTP-mocking dependency. Use whichever fixture matches the module under test's
HTTP library (see the aiohttp/httpx split noted above). Test files pair 1:1 with `hal_api`/
`hal_tools` modules (`test_hal_api_*.py`, `test_hal_tools_*.py`); `hal_tools` tests monkeypatch
the specific name the tool module imported its `hal_api` function as (e.g.
`tool_module._search_structure`), not the original `hal_api` function, since that's what's
actually called.

Local (no Docker):

```bash
pip install -r requirements.txt
python3 server.py
```

This starts the MCP server (`host=0.0.0.0`, `port=8000`) with the `streamable-http` transport.
`server.py` also exposes `app = mcp.streamable_http_app(stateless_http=True, host=HOST)` for
ASGI-server deployment (e.g. uvicorn/gunicorn) instead of the built-in `mcp.run()`. Note: in
`mcp>=2`, `host`/`port`/`stateless_http` are no longer `MCPServer(...)` constructor kwargs — they
must be passed to each of `run()` and `streamable_http_app()` individually, which is why they live
in `server.py` (the only place both are called) rather than in `core/mcp.py`.

Docker (see `docker/Dockerfile` + root `Makefile`, run `make help` for the full list):

```bash
make build   # docker build, TZ=<host tz> by default, override with TZ=Some/Zone
make up      # run detached, exposes port 8000
make logs    # follow logs
make down    # stop and remove the container
```

**Dependency note**: `requirements.txt` requires `mcp>=2.0.0`. `core/mcp.py` uses
`mcp.server.mcpserver.MCPServer` (the 2.x name for what was `mcp.server.fastmcp.FastMCP` in 1.x —
see `DECISIONS.md` for the migration and what changed).

## Architecture

Three-layer structure, one triplet per HAL capability:

- **`core/mcp.py`** — the single shared `MCPServer` instance (`mcp`), named `"hal"`. Everything
  else imports this singleton; there is exactly one MCP app for the whole server.
- **`hal_api/api_*.py`** — raw HTTP client functions with no MCP awareness. Each calls a HAL
  REST endpoint (`/search/`, `/ref/author/`, `/ref/structure/`) directly via `aiohttp` or
  `httpx` (both are used — not yet unified; check the target file's existing import before
  adding a new endpoint call), and returns a plain `dict`. On failure they return
  `{"error": ..., "query_url": ...}` rather than raising — callers must check for the `"error"`
  key rather than relying on exceptions.
- **`hal_tools/*.py`** — the `@mcp.tool()`-decorated wrappers that `server.py` imports for
  registration. Each wraps one (or, for `get_author_affiliations`, several chained) `hal_api`
  call(s), validates/normalizes inputs, and re-shapes the `hal_api` dict into the tool's
  documented return contract.
- **`utils.py`** — small cross-tool aggregation helpers (grouping publications by year/type,
  formatting keyword reports). Not tied to a single tool.

`server.py` is intentionally just an import manifest (`import hal_tools.X` for each tool,
side-effecting registration onto `mcp` via the decorator) plus the two run entrypoints — adding
a new tool means creating its `hal_api` + `hal_tools` pair and adding one import line here.

### Tool docstring contract

Tool docstrings (in `hal_tools/*.py`) are not just documentation — they are the primary interface
contract read by the LLM client at call time and follow a strict, consistent structure that new
tools must match:

- One-line purpose statement, then explicit **"UTILISER CET OUTIL"** / **"NE PAS utiliser"**
  sections cross-referencing the other tools that should be used instead for adjacent queries
  (e.g. `search_authors` docstring points to `get_author_affiliations` and
  `search_author_publications` for what it does *not* cover).
  This is how the tools stay disambiguated for the calling LLM — always update the docstrings of
  related tools when adding a new one that overlaps in scope.
- `Parameters:` / `Returns:` sections documenting the exact field names of the returned dict —
  these names come straight from the HAL API (e.g. `hal_id`, `docid`, `struct_id`) and must never
  be renamed/aliased in the docstring vs. the actual returned dict.
- A closing **"RÈGLES ANTI-HALLUCINATION"** / **"IMPORTANT - Règles anti-hallucination"** section:
  explicit instructions telling the calling LLM to report only what's in the structured fields,
  never invent an ID/name/affiliation from general knowledge, never silently pick one result among
  homonyms, and to surface `error`/`num_found == 0`/`has_more` as-is rather than reconstructing or
  estimating. Any new tool touching author/structure identity must carry the same discipline.

### Error/edge-case conventions in `hal_api`

- Never raise on HTTP failure or bad JSON — always return `{"error": "...", "query_url": ...}`
  (or `query_url: None` if the request never went out).
- Detect HAL returning HTML instead of JSON explicitly (seen in `api_get_author_affiliations.py`)
  rather than letting JSON parsing throw an unhelpful error.
- Derive field lists (`raw_fields_sample`) dynamically from the actual response rather than
  hardcoding assumed HAL schema fields.
- A `hal_tools` wrapper that chains multiple `hal_api` calls (e.g. resolve author → fetch
  affiliations per author) must produce a distinct, explicit error entry for missing
  precondition data (e.g. author with no `hal_id`) rather than silently skipping it — see the
  documented `continue`-with-explicit-error pattern in `hal_tools/get_author_affiliations.py`.

## Conventions specific to this repo

- Code (identifiers, comments) in English per user-global rules, but **tool docstrings and
  `README.md` are in French** — this is the established, intentional convention for this
  project (client-facing content for French-speaking HAL users), not an inconsistency to fix.
