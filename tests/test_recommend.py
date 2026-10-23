from toolhub.catalog import load_catalog
from toolhub.constraints import Constraints
from toolhub.recommend import compare

TOOLS = {t["slug"]: t for t in load_catalog()}


def test_compare_explains_exclusions_and_new_entries():
    before = Constraints(category="database")
    after = Constraints(category="database", hosting="self-hosted")
    result = compare(
        before,
        ["mongodb-atlas", "postgresql", "redis"],
        after,
        ["postgresql", "mongodb-community", "redis"],
        TOOLS,
    )
    by_slug = {i["slug"]: i for i in result["items"]}
    assert result["constraint_changes"] == ["hosting: any → self-hosted"]
    assert by_slug["mongodb-atlas"]["change"] == "excluded"
    assert "self-hosted" in by_slug["mongodb-atlas"]["reason"]
    assert by_slug["postgresql"]["change"] == "up"
    assert by_slug["mongodb-community"]["change"] == "new"
    assert "redis" not in by_slug


def test_compare_new_entry_previously_failing():
    before = Constraints(hosting="self-hosted")
    after = Constraints()
    result = compare(
        before,
        ["mongodb-community"],
        after,
        ["mongodb-atlas", "mongodb-community"],
        TOOLS,
    )
    new = next(i for i in result["items"] if i["slug"] == "mongodb-atlas")
    assert new["reason"].startswith("previously excluded")
