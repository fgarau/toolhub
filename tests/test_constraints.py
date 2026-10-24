import pytest

from toolhub.catalog import load_catalog
from toolhub.constraints import (
    Constraints,
    failures,
    matches,
    search_filters,
    vector_filter,
)

TOOLS = {t["slug"]: t for t in load_catalog()}


def evaluate_vector_filter(tool, f):
    """Tiny evaluator for the MQL subset produced by vector_filter."""
    if f is None:
        return True
    if "$and" in f:
        return all(evaluate_vector_filter(tool, c) for c in f["$and"])
    ((path, cond),) = f.items()
    value = tool[path]
    values = value if isinstance(value, list) else [value]
    if "$eq" in cond:
        return cond["$eq"] in values
    return bool(set(cond["$in"]) & set(values))


CASES = [
    Constraints(),
    Constraints(category="database", hosting="self-hosted"),
    Constraints(languages=("Python",), open_source_only=True),
    Constraints(hosting="managed", max_ops="low"),
    Constraints(category="realtime", capabilities=("offline-sync",)),
    Constraints(
        category="auth",
        languages=("TypeScript",),
        hosting="self-hosted",
        max_ops="medium",
    ),
]


@pytest.mark.parametrize("c", CASES)
def test_vector_filter_agrees_with_failures(c):
    for tool in TOOLS.values():
        assert evaluate_vector_filter(tool, vector_filter(c)) == (
            not failures(tool, c)
        ), tool["slug"]


def test_self_hosted_excludes_managed_only_services():
    c = Constraints(hosting="self-hosted")
    assert failures(TOOLS["mongodb-atlas"], c)
    assert not failures(TOOLS["mongodb-community"], c)
    assert "can be self-hosted" in matches(TOOLS["mongodb-community"], c)


def test_search_filters_cover_each_constraint():
    c = Constraints(
        category="ai",
        languages=("Go",),
        hosting="managed",
        open_source_only=True,
        max_ops="low",
        capabilities=("embeddings",),
    )
    paths = [next(iter(f.values()))["path"] for f in search_filters(c)]
    assert paths == [
        "category",
        "languages",
        "deployment",
        "open_source",
        "ops_overhead",
        "capabilities",
    ]
    assert search_filters(Constraints()) == []


def test_invalid_hosting_rejected():
    with pytest.raises(ValueError):
        Constraints(hosting="on-prem")
