from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from toolhub import catalog, embeddings
from toolhub.constraints import HOSTING_OPTIONS, Constraints
from toolhub.db import ConfigError, get_db
from toolhub.recommend import public, recommend

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ToolHub")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ConstraintsIn(BaseModel):
    category: str | None = None
    languages: list[str] = []
    hosting: str = "any"
    open_source_only: bool = False
    max_ops: str | None = None
    capabilities: list[str] = []


class PreviousIn(BaseModel):
    constraints: ConstraintsIn
    ranking: list[str]


class RecommendIn(BaseModel):
    brief: str = Field(min_length=1, max_length=2000)
    constraints: ConstraintsIn = ConstraintsIn()
    previous: PreviousIn | None = None
    limit: int = Field(default=5, ge=1, le=10)


def _db():
    try:
        return get_db()
    except ConfigError as e:
        raise HTTPException(503, str(e))


@app.exception_handler(PyMongoError)
async def mongo_error(request, exc: PyMongoError):
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": f"MongoDB error: {exc}"}, status_code=502)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/options")
def options():
    tools = _db()["tools"]
    caps = {
        category: sorted(tools.distinct("capabilities", {"category": category}))
        for category in catalog.CATEGORIES
    }
    languages = sorted(set(tools.distinct("languages")) - {"any"})
    return {
        "categories": list(catalog.CATEGORIES),
        "languages": languages,
        "capabilities": caps,
        "hosting": list(HOSTING_OPTIONS),
        "ops_levels": list(catalog.OPS_LEVELS),
        "tool_count": tools.count_documents({}),
        "embeddings": embeddings.mode(),
    }


@app.post("/api/recommend")
def recommend_endpoint(body: RecommendIn):
    try:
        c = Constraints.from_dict(body.constraints.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    previous = body.previous.model_dump() if body.previous else None
    try:
        return recommend(_db(), body.brief, c, embeddings.mode(), body.limit, previous)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/tools/{slug}")
def tool(slug: str):
    doc = _db()["tools"].find_one({"slug": slug})
    if not doc:
        raise HTTPException(404, "unknown tool")
    return public(doc)
