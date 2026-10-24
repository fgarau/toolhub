import json
from pathlib import Path

from pymongo import ReplaceOne
from pymongo.collection import Collection

from toolhub import embeddings

CATALOG_DIR = Path(__file__).parent / "data" / "catalog"
LAST_REVIEWED_AT = "2026-10-23"

CATEGORIES = (
    "database",
    "web-framework",
    "auth",
    "realtime",
    "queue",
    "observability",
    "deployment",
    "ai",
)
DEPLOYMENTS = ("library", "self-hosted", "managed-cloud")
OPS_LEVELS = ("low", "medium", "high")
REQUIRED_FIELDS = {
    "slug": str,
    "name": str,
    "category": str,
    "summary": str,
    "use_cases": str,
    "languages": list,
    "licence": str,
    "open_source": bool,
    "deployment": list,
    "ops_overhead": str,
    "capabilities": list,
    "tradeoffs": list,
    "avoid_if": str,
    "sources": list,
}


class CatalogError(ValueError):
    pass


def validate(tool: dict) -> None:
    slug = tool.get("slug", "<missing slug>")
    for field, kind in REQUIRED_FIELDS.items():
        if not isinstance(tool.get(field), kind):
            raise CatalogError(f"{slug}: '{field}' must be a {kind.__name__}")
    if tool["category"] not in CATEGORIES:
        raise CatalogError(f"{slug}: unknown category {tool['category']!r}")
    if not set(tool["deployment"]) <= set(DEPLOYMENTS) or not tool["deployment"]:
        raise CatalogError(
            f"{slug}: deployment must be a non-empty subset of {DEPLOYMENTS}"
        )
    if tool["ops_overhead"] not in OPS_LEVELS:
        raise CatalogError(f"{slug}: ops_overhead must be one of {OPS_LEVELS}")
    if not tool["sources"] or not all(
        s.get("title") and s.get("url", "").startswith("https://")
        for s in tool["sources"]
    ):
        raise CatalogError(f"{slug}: every tool needs https sources with titles")


def build_search_text(tool: dict) -> str:
    return " ".join(
        [
            f"{tool['name']} ({tool['category']}). {tool['summary']}",
            f"Use cases: {tool['use_cases']}",
            f"Capabilities: {', '.join(tool['capabilities'])}.",
            f"Languages: {', '.join(tool['languages'])}.",
            f"Deployment: {', '.join(tool['deployment'])}. Licence: {tool['licence']}.",
            f"Operational overhead: {tool['ops_overhead']}.",
            f"Trade-offs: {' '.join(tool['tradeoffs'])}",
            f"Avoid if {tool['avoid_if']}",
        ]
    )


def load_catalog(directory: Path = CATALOG_DIR) -> list[dict]:
    tools = []
    for path in sorted(directory.glob("*.json")):
        tools.extend(json.loads(path.read_text()))
    slugs = set()
    for tool in tools:
        validate(tool)
        if tool["slug"] in slugs:
            raise CatalogError(f"duplicate slug {tool['slug']!r}")
        slugs.add(tool["slug"])
        tool["search_text"] = build_search_text(tool)
        tool.setdefault("last_reviewed_at", LAST_REVIEWED_AT)
    return tools


def seed(collection: Collection, tools: list[dict], mode: str) -> dict:
    ops = []
    for tool in tools:
        doc = dict(tool)
        if mode == embeddings.HASH:
            doc["embedding"] = embeddings.hash_embed(doc["search_text"])
        ops.append(ReplaceOne({"slug": doc["slug"]}, doc, upsert=True))
    result = collection.bulk_write(ops)
    removed = collection.delete_many(
        {"slug": {"$nin": [t["slug"] for t in tools]}}
    ).deleted_count
    collection.create_index("slug", unique=True)
    return {
        "upserted": result.upserted_count,
        "updated": result.modified_count,
        "removed": removed,
        "total": len(tools),
    }
