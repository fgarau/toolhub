# ToolHub

Encode London 2026 · MongoDB Atlas track.

ToolHub helps developers choose the right library, framework, database or service for a specific product problem. Instead of a popularity list, it returns a short, auditable recommendation: what fits, why, the trade-offs, and the source evidence. When a constraint changes (e.g. "must self-host"), results re-rank and the change is explained.

## How it works

1. The developer writes a brief and selects hard constraints (language, licence, deployment model, etc.).
2. ToolHub retrieves a shortlist from a curated catalogue (30–50 tools) stored in MongoDB Atlas, using:
   - **Atlas Search** for exact filters and terms,
   - **Vector Search / Automated Embedding** for semantic matching against the brief,
   - **Hybrid Search** to fuse both.
3. Each result shows a fit score, matched constraints, a rationale, trade-offs and source links. Strong candidates that fail a hard constraint are shown as excluded.

Stretch: Atlas Stream Processing to flag recommendations as stale when release/ecosystem evidence changes.

## Cataloguing approach

The catalogue is curated by hand rather than crawled. `docs/Cataloging GitHub Repositories.pdf` (Sharma et al., EASE '17) is the background reference: it extracts functionality-descriptive text from repository READMEs and groups projects into categories with LDA-GA topic modelling. We borrow the idea of a concise functionality description per repo (our `search_text`) and of categories as the grouping axis. Semantic retrieval via embeddings replaces topic modelling.

## Docs

- `docs/PROJECT_BRIEF.md`: scope, data model, retrieval approach, demo narrative, acceptance criteria.
- `docs/Cataloging GitHub Repositories.pdf`: background paper.

## Setup

Python project managed with [uv](https://docs.astral.sh/uv/) (Python ≥ 3.15).

### MongoDB connection

Atlas credentials live in a local `.env` file (gitignored) or in environment variables. Never commit connection strings or API keys.

```sh
# .env
MONGODB_URI="mongodb+srv://<user>:<password>@cluster1.3ze1yu.mongodb.net/"
MONGODB_DB=toolhub   # optional, defaults to "toolhub"
```

URL-encode special characters in the password (`@ : / ? # %`). The Atlas user and its IP allowlist entry are managed under Security → Database Access / Network Access.

`src/toolhub/db.py` loads `.env` (via `python-dotenv`) and exposes `get_client()` (a cached `pymongo` client using the stable server API) and `get_db()`. Check connectivity with:

```sh
uv sync
uv run toolhub ping         # exit 0 connected, 1 unreachable/auth failure, 2 MONGODB_URI not set
uv run toolhub setup        # seed the catalogue + create Atlas Search / Vector Search indexes
uv run toolhub serve        # http://127.0.0.1:8000
```

### Commands

| Command | What it does |
| --- | --- |
| `toolhub seed` | Upserts the curated catalogue (`src/toolhub/data/catalog/*.json`) into the `tools` collection and builds each tool's `search_text`. |
| `toolhub indexes` | Creates/updates the `tools_search` (Atlas Search) and `tools_vector` (Vector Search) indexes and waits until they are queryable. |
| `toolhub setup` | `seed` + `indexes`. |
| `toolhub recommend "<brief>" [--category …] [--language …] [--hosting self-hosted\|managed] [--open-source-only] [--max-ops low\|medium\|high] [--capability …]` | Prints recommendations as JSON. |
| `toolhub serve` | Runs the web UI and API. |

### Embeddings

`TOOLHUB_EMBEDDINGS` selects how the semantic side works:

- `auto` (default): **Atlas Automated Embedding**. The `tools_vector` index is an `autoEmbed` index on `search_text` (model from `TOOLHUB_EMBED_MODEL`, default `voyage-4`), and queries send the brief as text. Atlas generates and maintains the embeddings. This is an Atlas preview feature; enable it on the cluster first.
- `hash`: offline fallback for local development without Voyage AI. Seed stores a 256-dim hashed bag-of-words vector in `embedding` and the index is a plain `vector` index. It is lexical, not semantic, so use `auto` for the demo.

Re-run `toolhub setup` after switching modes.

### Local development without Atlas

```sh
docker run -d --name toolhub-atlas -p 27017:27017 mongodb/mongodb-atlas-local
export MONGODB_URI='mongodb://localhost:27017/?directConnection=true' TOOLHUB_EMBEDDINGS=hash
uv run toolhub setup && uv run toolhub serve
```

### Tests

```sh
uv run pytest                                   # unit tests
TOOLHUB_INTEGRATION=1 uv run pytest             # + end-to-end against $MONGODB_URI (seeds the db)
uvx ruff check src tests && uvx ruff format --check src tests
```

## Architecture

- `catalog.py`: loads and validates the curated catalogue (52 tools across 8 categories) and seeds the `tools` collection.
- `indexes.py`: Atlas Search index (English-analysed text fields plus `token` fields for filters) and Vector Search index (`autoEmbed` or `vector`, plus `filter` fields).
- `constraints.py`: hard constraints (category, languages, hosting, open source, max ops overhead, required capabilities). Each is translated into Atlas Search `compound.filter` clauses and a `$vectorSearch` pre-filter, so excluded tools never enter either ranking. A Python version of the same rules explains exclusions.
- `search.py`: one aggregation using `$rankFusion` (reciprocal rank fusion, MongoDB 8.0+) over a `$search` pipeline (keyword) and a `$vectorSearch` pipeline (semantic), with `scoreDetails` to report each tool's rank in each input.
- `recommend.py`: fit score (fusion score relative to the top hit), matched constraints, rationale, "strong candidates excluded by your constraints" (the same search without hard constraints), and the diff against the previous ranking when a constraint changes. Every query is logged to the `queries` collection.
- `web.py` + `static/`: FastAPI API (`/api/options`, `/api/recommend`, `/api/tools/{slug}`) and a single-page UI. Re-submitting the same brief with different constraints shows a "What changed" panel, and the exact Atlas pipeline is shown under the results.

## Status

MVP: catalogue, indexes, hybrid retrieval, API and UI. Tested end-to-end against the `mongodb-atlas-local` image in `hash` mode; Automated Embedding (`auto`) still needs to be verified on a real Atlas cluster.
