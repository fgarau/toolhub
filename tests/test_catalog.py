from toolhub import catalog, embeddings


def test_catalog_loads_and_validates():
    tools = catalog.load_catalog()
    assert 30 <= len(tools) <= 80
    assert len({t["slug"] for t in tools}) == len(tools)
    assert {t["category"] for t in tools} == set(catalog.CATEGORIES)
    for tool in tools:
        assert tool["name"] in tool["search_text"]
        assert tool["last_reviewed_at"]


def test_hash_embedding_is_normalised_and_deterministic():
    a = embeddings.hash_embed("offline sync for collaborative editing")
    assert a == embeddings.hash_embed("offline sync for collaborative editing")
    assert len(a) == embeddings.HASH_DIMENSIONS
    assert abs(sum(v * v for v in a) - 1) < 1e-9
