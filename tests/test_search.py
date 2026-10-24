from toolhub import embeddings
from toolhub.constraints import Constraints
from toolhub.search import hybrid_pipeline, pipeline_ranks, redact_pipeline


def test_hybrid_pipeline_uses_rank_fusion_with_both_inputs():
    c = Constraints(category="database", hosting="self-hosted")
    pipeline = hybrid_pipeline("vector search", c, 5, embeddings.AUTO)
    fusion = pipeline[0]["$rankFusion"]
    keyword = fusion["input"]["pipelines"]["keyword"][0]["$search"]
    semantic = fusion["input"]["pipelines"]["semantic"][0]["$vectorSearch"]
    assert keyword["compound"]["filter"]
    assert semantic["query"] == {"text": "vector search"}
    assert semantic["path"] == "search_text"
    assert "$and" in semantic["filter"]


def test_hash_mode_uses_query_vector_and_redacts_it():
    pipeline = hybrid_pipeline("queues", Constraints(), 5, embeddings.HASH)
    semantic = pipeline[0]["$rankFusion"]["input"]["pipelines"]["semantic"][0][
        "$vectorSearch"
    ]
    assert len(semantic["queryVector"]) == embeddings.HASH_DIMENSIONS
    assert "filter" not in semantic
    redacted = redact_pipeline(pipeline)
    assert redacted[0]["$rankFusion"]["input"]["pipelines"]["semantic"][0][
        "$vectorSearch"
    ]["queryVector"].startswith("<")


def test_pipeline_ranks_parses_score_details():
    details = {
        "details": [
            {"inputPipelineName": "keyword", "rank": 2},
            {"inputPipelineName": "semantic", "rank": 0},
        ]
    }
    assert pipeline_ranks(details) == {"keyword": 2}
    assert pipeline_ranks(None) == {}
