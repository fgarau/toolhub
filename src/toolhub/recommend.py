import re
from datetime import UTC, datetime

from pymongo.database import Database

from toolhub.constraints import Constraints, failures, matches
from toolhub.search import (
    KEYWORD,
    SEMANTIC,
    hybrid_search,
    pipeline_ranks,
    redact_pipeline,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "in",
    "is",
    "it",
    "need",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "we",
    "with",
    "app",
    "team",
    "building",
    "want",
    "must",
}
PUBLIC_FIELDS = (
    "slug",
    "name",
    "category",
    "summary",
    "use_cases",
    "languages",
    "licence",
    "open_source",
    "deployment",
    "ops_overhead",
    "capabilities",
    "tradeoffs",
    "avoid_if",
    "sources",
    "last_reviewed_at",
)


def public(tool: dict) -> dict:
    return {k: tool[k] for k in PUBLIC_FIELDS if k in tool}


def brief_terms(brief: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", brief.lower())
        if w not in STOPWORDS and len(w) > 2
    }


def brief_evidence(tool: dict, brief: str) -> list[str]:
    terms = brief_terms(brief)
    hits = []
    for cap in tool["capabilities"]:
        if terms & set(cap.split("-")):
            hits.append(cap)
    return hits


def retrieval_summary(ranks: dict[str, int]) -> str:
    parts = []
    if KEYWORD in ranks:
        parts.append(f"#{ranks[KEYWORD]} in keyword search")
    if SEMANTIC in ranks:
        parts.append(f"#{ranks[SEMANTIC]} in semantic search")
    return " and ".join(parts) if parts else "retrieved by hybrid search"


def rationale(tool: dict, c: Constraints, brief: str, ranks: dict[str, int]) -> str:
    sentences = [tool["summary"]]
    evidence = brief_evidence(tool, brief)
    if evidence:
        sentences.append(f"Matches your brief on: {', '.join(evidence)}.")
    met = matches(tool, c)
    if met:
        sentences.append(f"Meets your constraints: {'; '.join(met)}.")
    sentences.append(f"Ranked {retrieval_summary(ranks)}.")
    return " ".join(sentences)


def build_result(
    hit: dict, position: int, top_score: float, c: Constraints, brief: str
) -> dict:
    ranks = pipeline_ranks(hit.get("score_details"))
    score = hit.get("fusion_score") or 0.0
    return {
        "rank": position,
        "tool": public(hit),
        "fit_score": round(100 * score / top_score) if top_score else 0,
        "fusion_score": score,
        "pipeline_ranks": ranks,
        "matched_constraints": matches(hit, c),
        "brief_evidence": brief_evidence(hit, brief),
        "rationale": rationale(hit, c, brief, ranks),
    }


def recommend(
    db: Database,
    brief: str,
    c: Constraints,
    mode: str,
    limit: int = 5,
    previous: dict | None = None,
) -> dict:
    brief = brief.strip()
    if not brief:
        raise ValueError("brief must not be empty")
    tools = db["tools"]
    hits, pipeline = hybrid_search(tools, brief, c, limit, mode)
    top = hits[0].get("fusion_score", 0.0) if hits else 0.0
    results = [build_result(h, i + 1, top, c, brief) for i, h in enumerate(hits)]

    broad_constraints = Constraints(category=c.category)
    broad, _ = hybrid_search(tools, brief, broad_constraints, limit * 2, mode)
    kept = {h["slug"] for h in hits}
    excluded = [
        {
            "tool": public(t),
            "rank_without_constraints": i + 1,
            "reasons": failures(t, c),
        }
        for i, t in enumerate(broad)
        if t["slug"] not in kept and failures(t, c)
    ][:3]

    response = {
        "brief": brief,
        "constraints": c.to_dict(),
        "results": results,
        "excluded": excluded,
        "retrieval": {"mode": mode, "pipeline": redact_pipeline(pipeline)},
    }
    if previous:
        prev_c = Constraints.from_dict(previous.get("constraints"))
        prev_ranking = list(previous.get("ranking") or [])
        slugs = set(prev_ranking) | kept
        by_slug = {
            t["slug"]: t
            for t in tools.find({"slug": {"$in": list(slugs)}}, {"embedding": 0})
        }
        response["changes"] = compare(
            prev_c, prev_ranking, c, [r["tool"]["slug"] for r in results], by_slug
        )

    db["queries"].insert_one(
        {
            "brief": brief,
            "hard_constraints": c.to_dict(),
            "result_slugs": [r["tool"]["slug"] for r in results],
            "created_at": datetime.now(UTC),
        }
    )
    return response


def constraint_changes(before: Constraints, after: Constraints) -> list[str]:
    b, a = before.to_dict(), after.to_dict()
    changes = []
    for key in b:
        if b[key] != a[key]:
            changes.append(f"{key}: {_fmt(b[key])} → {_fmt(a[key])}")
    return changes


def _fmt(value) -> str:
    if value in (None, [], "any", False):
        return "any" if value is not False else "no"
    if value is True:
        return "yes"
    return ", ".join(value) if isinstance(value, list) else str(value)


def compare(
    before: Constraints,
    prev_ranking: list[str],
    after: Constraints,
    ranking: list[str],
    tools: dict[str, dict],
) -> dict:
    items = []
    for old_pos, slug in enumerate(prev_ranking, start=1):
        tool = tools.get(slug)
        name = tool["name"] if tool else slug
        if slug in ranking:
            new_pos = ranking.index(slug) + 1
            if new_pos == old_pos:
                continue
            direction = "up" if new_pos < old_pos else "down"
            items.append(
                {
                    "slug": slug,
                    "name": name,
                    "change": direction,
                    "before": old_pos,
                    "after": new_pos,
                    "reason": f"moved {direction} from #{old_pos} to #{new_pos} as the shortlist changed",
                }
            )
        else:
            reasons = failures(tool, after) if tool else []
            items.append(
                {
                    "slug": slug,
                    "name": name,
                    "change": "excluded" if reasons else "dropped",
                    "before": old_pos,
                    "after": None,
                    "reason": f"excluded: it {'; '.join(reasons)}"
                    if reasons
                    else "fell out of the top results",
                }
            )
    for new_pos, slug in enumerate(ranking, start=1):
        if slug in prev_ranking:
            continue
        tool = tools.get(slug)
        name = tool["name"] if tool else slug
        prev_fail = failures(tool, before) if tool else []
        reason = (
            f"previously excluded because it {'; '.join(prev_fail)}"
            if prev_fail
            else "moved into the shortlist after other options were excluded"
        )
        items.append(
            {
                "slug": slug,
                "name": name,
                "change": "new",
                "before": None,
                "after": new_pos,
                "reason": reason,
            }
        )
    return {"constraint_changes": constraint_changes(before, after), "items": items}
