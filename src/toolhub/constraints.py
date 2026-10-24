from dataclasses import asdict, dataclass, field

from toolhub.catalog import OPS_LEVELS

HOSTING_OPTIONS = {
    "any": None,
    "self-hosted": ("self-hosted", "library"),
    "managed": ("managed-cloud",),
}
HOSTING_LABELS = {
    "self-hosted": "can be self-hosted",
    "managed": "available as a managed service",
}
ANY_LANGUAGE = "any"


@dataclass(frozen=True)
class Constraints:
    category: str | None = None
    languages: tuple[str, ...] = ()
    hosting: str = "any"
    open_source_only: bool = False
    max_ops: str | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.hosting not in HOSTING_OPTIONS:
            raise ValueError(f"hosting must be one of {tuple(HOSTING_OPTIONS)}")
        if self.max_ops is not None and self.max_ops not in OPS_LEVELS:
            raise ValueError(f"max_ops must be one of {OPS_LEVELS}")

    @classmethod
    def from_dict(cls, data: dict | None) -> Constraints:
        data = data or {}
        return cls(
            category=data.get("category") or None,
            languages=tuple(data.get("languages") or ()),
            hosting=data.get("hosting") or "any",
            open_source_only=bool(data.get("open_source_only")),
            max_ops=data.get("max_ops") or None,
            capabilities=tuple(data.get("capabilities") or ()),
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["languages"] = list(self.languages)
        data["capabilities"] = list(self.capabilities)
        return data

    def allowed_deployments(self) -> tuple[str, ...] | None:
        return HOSTING_OPTIONS[self.hosting]

    def allowed_ops(self) -> tuple[str, ...] | None:
        if self.max_ops is None:
            return None
        return OPS_LEVELS[: OPS_LEVELS.index(self.max_ops) + 1]


def failures(tool: dict, c: Constraints) -> list[str]:
    reasons = []
    if c.category and tool["category"] != c.category:
        reasons.append(f"is a {tool['category']} tool, not {c.category}")
    if c.languages and not (
        ANY_LANGUAGE in tool["languages"] or set(c.languages) & set(tool["languages"])
    ):
        reasons.append(f"has no official support for {' or '.join(c.languages)}")
    allowed = c.allowed_deployments()
    if allowed and not set(allowed) & set(tool["deployment"]):
        reasons.append(
            f"cannot be {'self-hosted' if c.hosting == 'self-hosted' else 'used as a managed service'}"
            f" (deployment: {', '.join(tool['deployment'])})"
        )
    if c.open_source_only and not tool["open_source"]:
        reasons.append(f"is not open source (licence: {tool['licence']})")
    ops = c.allowed_ops()
    if ops and tool["ops_overhead"] not in ops:
        reasons.append(
            f"has {tool['ops_overhead']} operational overhead (max: {c.max_ops})"
        )
    missing = [cap for cap in c.capabilities if cap not in tool["capabilities"]]
    if missing:
        reasons.append(f"lacks {', '.join(missing)}")
    return reasons


def matches(tool: dict, c: Constraints) -> list[str]:
    met = []
    if c.languages:
        langs = [lang for lang in c.languages if lang in tool["languages"]]
        met.append(
            f"supports {', '.join(langs)}"
            if langs
            else "language-agnostic (any client)"
        )
    if c.hosting != "any":
        met.append(HOSTING_LABELS[c.hosting])
    if c.open_source_only:
        met.append(f"open source ({tool['licence']})")
    if c.max_ops:
        met.append(f"{tool['ops_overhead']} operational overhead")
    met.extend(f"has {cap}" for cap in c.capabilities)
    return met


def search_filters(c: Constraints) -> list[dict]:
    """Atlas Search ``compound.filter`` clauses equivalent to :func:`failures`."""
    clauses = []
    if c.category:
        clauses.append({"equals": {"path": "category", "value": c.category}})
    if c.languages:
        clauses.append(
            {"in": {"path": "languages", "value": [*c.languages, ANY_LANGUAGE]}}
        )
    if allowed := c.allowed_deployments():
        clauses.append({"in": {"path": "deployment", "value": list(allowed)}})
    if c.open_source_only:
        clauses.append({"equals": {"path": "open_source", "value": True}})
    if ops := c.allowed_ops():
        clauses.append({"in": {"path": "ops_overhead", "value": list(ops)}})
    clauses.extend(
        {"equals": {"path": "capabilities", "value": cap}} for cap in c.capabilities
    )
    return clauses


def vector_filter(c: Constraints) -> dict | None:
    """``$vectorSearch`` pre-filter equivalent to :func:`failures`."""
    clauses = []
    if c.category:
        clauses.append({"category": {"$eq": c.category}})
    if c.languages:
        clauses.append({"languages": {"$in": [*c.languages, ANY_LANGUAGE]}})
    if allowed := c.allowed_deployments():
        clauses.append({"deployment": {"$in": list(allowed)}})
    if c.open_source_only:
        clauses.append({"open_source": {"$eq": True}})
    if ops := c.allowed_ops():
        clauses.append({"ops_overhead": {"$in": list(ops)}})
    clauses.extend({"capabilities": {"$eq": cap}} for cap in c.capabilities)
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}
