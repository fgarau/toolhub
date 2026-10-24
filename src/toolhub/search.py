from pymongo.collection import Collection

from toolhub import embeddings
from toolhub.constraints import Constraints, search_filters, vector_filter
from toolhub.indexes import SEARCH_INDEX, VECTOR_INDEX

KEYWORD = "keyword"
SEMANTIC = "semantic"
TEXT_PATHS = ["name", "summary", "use_cases", "search_text", "capabilities"]


def keyword_pipeline(brief: str, c: Constraints, limit: int) -> list[dict]:
    compound = {
        "should": [
            {
                "text": {
                    "query": brief,
                    "path": "name",
                    "score": {"boost": {"value": 3}},
                }
            },
            {"text": {"query": brief, "path": TEXT_PATHS, "fuzzy": {"maxEdits": 1}}},
        ],
        "minimumShouldMatch": 1,
    }
    if filters := search_filters(c):
        compound["filter"] = filters
    return [
        {"$search": {"index": SEARCH_INDEX, "compound": compound}},
        {"$limit": limit},
    ]


def semantic_pipeline(brief: str, c: Constraints, limit: int, mode: str) -> list[dict]:
    stage = {
        "index": VECTOR_INDEX,
        "limit": limit,
        "numCandidates": max(100, limit * 20),
    }
    if mode == embeddings.AUTO:
        stage |= {"path": "search_text", "query": {"text": brief}}
    else:
        stage |= {"path": "embedding", "queryVector": embeddings.hash_embed(brief)}
    if (vfilter := vector_filter(c)) is not None:
        stage["filter"] = vfilter
    return [{"$vectorSearch": stage}]


def hybrid_pipeline(
    brief: str, c: Constraints, limit: int, mode: str, weights: dict | None = None
) -> list[dict]:
    candidates = limit * 3
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        KEYWORD: keyword_pipeline(brief, c, candidates),
                        SEMANTIC: semantic_pipeline(brief, c, candidates, mode),
                    }
                },
                "combination": {"weights": weights or {KEYWORD: 1, SEMANTIC: 1}},
                "scoreDetails": True,
            }
        },
        {
            "$addFields": {
                "fusion_score": {"$meta": "score"},
                "score_details": {"$meta": "scoreDetails"},
            }
        },
        {"$limit": limit},
        {"$project": {"embedding": 0}},
    ]


def pipeline_ranks(score_details: dict | None) -> dict[str, int]:
    ranks = {}
    for detail in (score_details or {}).get("details", []):
        name, rank = detail.get("inputPipelineName"), detail.get("rank")
        if name and isinstance(rank, int) and rank > 0:
            ranks[name] = rank
    return ranks


def hybrid_search(
    collection: Collection, brief: str, c: Constraints, limit: int, mode: str
) -> tuple[list[dict], list[dict]]:
    pipeline = hybrid_pipeline(brief, c, limit, mode)
    return list(collection.aggregate(pipeline)), pipeline


def redact_pipeline(pipeline: list[dict]) -> list[dict]:
    """Shorten query vectors so the pipeline can be shown in the UI."""

    def walk(value):
        if isinstance(value, dict):
            return {
                k: (f"<{len(v)}-dim vector>" if k == "queryVector" else walk(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    return walk(pipeline)
