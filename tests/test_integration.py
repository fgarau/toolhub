"""End-to-end test against a real deployment.

Run with e.g. an Atlas Local container:
  docker run -d -p 27017:27017 mongodb/mongodb-atlas-local
  TOOLHUB_INTEGRATION=1 TOOLHUB_EMBEDDINGS=hash \
    MONGODB_URI='mongodb://localhost:27017/?directConnection=true' uv run pytest
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLHUB_INTEGRATION"), reason="set TOOLHUB_INTEGRATION=1"
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from toolhub import catalog, embeddings, indexes
    from toolhub.db import get_db

    tools = get_db()["tools"]
    catalog.seed(tools, catalog.load_catalog(), embeddings.mode())
    indexes.ensure_indexes(tools, embeddings.mode())
    from toolhub.web import app

    return TestClient(app)


def test_constraint_change_reranks(client):
    brief = "managed document database with vector search for an AI app"
    first = client.post(
        "/api/recommend", json={"brief": brief, "constraints": {"category": "database"}}
    )
    assert first.status_code == 200, first.text
    ranking = [r["tool"]["slug"] for r in first.json()["results"]]
    assert "mongodb-atlas" in ranking

    second = client.post(
        "/api/recommend",
        json={
            "brief": brief,
            "constraints": {"category": "database", "hosting": "self-hosted"},
            "previous": {"constraints": {"category": "database"}, "ranking": ranking},
        },
    )
    body = second.json()
    slugs = [r["tool"]["slug"] for r in body["results"]]
    assert "mongodb-atlas" not in slugs
    assert any(e["tool"]["slug"] == "mongodb-atlas" for e in body["excluded"])
    change = next(i for i in body["changes"]["items"] if i["slug"] == "mongodb-atlas")
    assert change["change"] == "excluded"


def test_options(client):
    data = client.get("/api/options").json()
    assert data["tool_count"] >= 30
    assert "Python" in data["languages"]
