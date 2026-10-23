# ToolHub — Encode London 2026 / MongoDB Atlas Track

## Intent

ToolHub helps developers choose the right library, framework, language, database, or service for a specific product problem. Instead of producing an ungrounded list of popular tools, it returns a short, auditable recommendation: what fits, why it fits, the trade-offs, and the source evidence.

Example request:

> "We are a two-person TypeScript team building an offline-capable real-time collaboration app. We need low operational overhead and an open-source-friendly path."

The product ranks suitable options and stacks, highlights any hard-constraint conflicts, and explains why a result changed when the developer adjusts a requirement.

## Hackathon objective

Build a working web MVP for the **MongoDB Atlas** track. MongoDB Atlas must be indispensable: it stores the tool catalogue and evidence, and powers the retrieval/ranking experience.

Use these Atlas features in the demo:

1. **Atlas Search** for exact requirements and filters: language, licence, deployment model, category, SDK support, pricing tier, offline capability, etc.
2. **Automated Embedding / Atlas Vector Search** for semantic matching between a developer's brief and tool descriptions, use cases, and caveats.
3. **Hybrid Search** to combine semantic relevance with exact hard constraints.
4. **Stretch: Atlas Stream Processing** to ingest a small feed of release or ecosystem updates and mark recommendations as stale when their evidence changes.

Do not describe this as "a chatbot for developer tools." The differentiator is evidence-backed, constraint-aware decisions.

## MVP user flow

1. Developer writes a brief and selects a few hard constraints.
2. ToolHub retrieves and ranks a shortlist of tools or stack combinations.
3. Each result shows:
   - fit score and matched constraints;
   - a plain-language rationale;
   - trade-offs / a "do not choose this if…" caveat;
   - links or excerpts from the catalogue's source evidence.
4. Developer changes one constraint, for example from "managed service is fine" to "must self-host".
5. Results re-rank and ToolHub explains the material change.

## Initial scope

Seed a curated catalogue of 30–50 entries rather than attempting to crawl the whole ecosystem. Prioritise categories that make coherent stack recommendations:

- Web frameworks: Next.js, React, Remix, SvelteKit, FastAPI, Django.
- Databases and backend: MongoDB Atlas, PostgreSQL, Supabase, Firebase, Redis.
- Auth: Auth0, Clerk, Better Auth, Keycloak.
- Realtime, queues, observability, deployment, and AI tooling.

For each entry, capture factual metadata plus a concise, manually-curated `search_text` made of: what it is, ideal use cases, constraints, operational trade-offs, and source links.

Focus the MVP on recommendations for a single technology category first. Add stack-level recommendations only if retrieval and explanation are already reliable.

## Suggested data model

`tools`

```json
{
  "name": "MongoDB Atlas",
  "slug": "mongodb-atlas",
  "category": "database",
  "languages": ["TypeScript", "Python", "Java", "Go"],
  "licence": "proprietary-managed-service",
  "deployment": ["managed-cloud"],
  "capabilities": ["document-model", "full-text-search", "vector-search", "realtime"],
  "constraints": ["cloud-account-required"],
  "search_text": "…curated product and trade-off description…",
  "sources": [{ "title": "Official documentation", "url": "https://…" }],
  "last_reviewed_at": "2026-10-23"
}
```

`queries` (optional)

```json
{
  "brief": "…",
  "hard_constraints": { "languages": ["TypeScript"], "self_hosted": false },
  "created_at": "…"
}
```

`evidence` may be a separate collection if an entry needs multiple detailed evidence snippets. Keep the first implementation simple: embed a small source list in each tool document.

## Retrieval approach

- Apply hard filters before or within search where appropriate (for example required language or self-hosting).
- Run lexical Atlas Search over metadata and `search_text` for precise terms.
- Run Vector Search over the developer brief against the semantically embedded `search_text`.
- Fuse both results using Atlas hybrid search; retain enough retrieval metadata to explain the match.
- Keep scoring transparent. Never present an unsupported claim as a fact.

The UI should distinguish:

- **Matches your brief** — evidence and constraints that support the choice.
- **Trade-offs** — known compromises.
- **Excluded** — a strong candidate that failed a hard requirement, if useful for comparison.

## Architecture

```text
Browser UI
  → API / recommendation service
    → MongoDB Atlas
        ├─ tool catalogue + evidence
        ├─ Atlas Search index
        ├─ Automated Embedding / Vector Search index
        └─ hybrid retrieval and ranking
```

Use the existing Python project as the backend starting point unless a different frontend stack is deliberately chosen. Keep credentials in local environment variables; never commit connection strings or API keys.

## Demo narrative (three minutes)

1. Introduce a developer with a concrete brief and non-negotiable constraints.
2. Submit the brief and show ToolHub's ranked recommendations.
3. Open the top result to show matched constraints, sources, and caveats.
4. Change one constraint (e.g. "must self-host").
5. Show the new order and explain why the former recommendation was excluded or demoted.
6. Briefly show the Atlas collection and search/vector indexes to make the MongoDB integration tangible.

## Acceptance criteria

- A user can submit a natural-language brief plus at least two structured constraints.
- Results are retrieved from MongoDB Atlas and show evidence from the stored catalogue.
- At least one Atlas Search, Vector Search/Automated Embedding, and Hybrid Search query is demonstrably used.
- Results adapt to a changed constraint.
- The repository has a clear README and setup steps.
- A three-minute demo video shows the application and MongoDB usage.

## Non-goals for the first version

- Exhaustive coverage of the developer-tool ecosystem.
- Automated web crawling, recommendation claims without sources, or live pricing comparisons.
- A general-purpose conversational assistant.
- Stream processing before the retrieval experience is complete.

## First implementation tasks

1. Provision Atlas, create the database and restricted application user, and configure local environment variables.
2. Define the `tools` schema and seed a small, high-quality catalogue.
3. Create and validate Atlas Search plus Automated Embedding / Vector Search indexes.
4. Implement a hybrid-search endpoint returning explanations and source metadata.
5. Build the brief/constraint form and ranked-result cards.
6. Add the constraint-change comparison state and rehearse the demo.
