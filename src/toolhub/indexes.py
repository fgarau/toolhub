import time

from pymongo.collection import Collection
from pymongo.operations import SearchIndexModel

from toolhub import embeddings

SEARCH_INDEX = "tools_search"
VECTOR_INDEX = "tools_vector"
FILTER_FIELDS = (
    "category",
    "languages",
    "deployment",
    "open_source",
    "ops_overhead",
    "capabilities",
)


def search_index_definition() -> dict:
    text = {"type": "string", "analyzer": "lucene.english"}
    return {
        "mappings": {
            "dynamic": False,
            "fields": {
                "name": text,
                "summary": text,
                "use_cases": text,
                "search_text": text,
                "capabilities": [{"type": "token"}, text],
                "category": {"type": "token"},
                "languages": {"type": "token"},
                "deployment": {"type": "token"},
                "ops_overhead": {"type": "token"},
                "open_source": {"type": "boolean"},
            },
        }
    }


def vector_index_definition(mode: str) -> dict:
    if mode == embeddings.AUTO:
        embedded = {
            "type": "autoEmbed",
            "modality": "text",
            "path": "search_text",
            "model": embeddings.model(),
        }
    else:
        embedded = {
            "type": "vector",
            "path": "embedding",
            "numDimensions": embeddings.HASH_DIMENSIONS,
            "similarity": "cosine",
        }
    return {
        "fields": [embedded, *({"type": "filter", "path": f} for f in FILTER_FIELDS)]
    }


def ensure_indexes(
    collection: Collection, mode: str, wait: bool = True, timeout: float = 600
) -> list[str]:
    wanted = {
        SEARCH_INDEX: ("search", search_index_definition()),
        VECTOR_INDEX: ("vectorSearch", vector_index_definition(mode)),
    }
    existing = {i["name"]: i for i in collection.list_search_indexes()}
    actions = []
    for name, (kind, definition) in wanted.items():
        current = existing.get(name)
        if current is None:
            collection.create_search_index(
                SearchIndexModel(definition=definition, name=name, type=kind)
            )
            actions.append(f"created {name}")
        elif current.get("latestDefinition") != definition:
            collection.update_search_index(name, definition)
            actions.append(f"updated {name}")
        else:
            actions.append(f"{name} unchanged")
    if wait:
        wait_until_queryable(collection, list(wanted), timeout)
    return actions


def wait_until_queryable(
    collection: Collection, names: list[str], timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        indexes = {i["name"]: i for i in collection.list_search_indexes()}
        if all(
            indexes.get(n, {}).get("queryable") and indexes[n].get("status") == "READY"
            for n in names
        ):
            return
        if time.monotonic() > deadline:
            states = {n: indexes.get(n, {}).get("status") for n in names}
            raise TimeoutError(f"search indexes not ready: {states}")
        time.sleep(2)
