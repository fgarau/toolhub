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

```sh
uv sync
uv run toolhub
```

### MongoDB connection

Atlas credentials live in a local `.env` file (gitignored). Never commit connection strings or API keys.

```sh
# .env
MONGODB_URI="mongodb+srv://<user>:<password>@cluster1.3ze1yu.mongodb.net/"
```

URL-encode special characters in the password (`@ : / ? # %`). The Atlas user and its IP allowlist entry are managed under Security → Database Access / Network Access.

`src/toolhub/db.py` loads `.env` (via `python-dotenv`) and exposes `get_client()`, which returns a `pymongo` client using the stable server API. Check connectivity with:

```sh
uv run python -m toolhub.db   # prints "Connected to cluster1"
```

## Status

Early scaffolding. Atlas cluster (`cluster1`) is provisioned and reachable. Next steps: define the `tools` schema, seed the catalogue, create search and vector indexes, build the hybrid-search endpoint and UI.
