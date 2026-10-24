import argparse
import json
import sys

from pymongo.errors import PyMongoError


def main() -> None:
    parser = argparse.ArgumentParser(prog="toolhub")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ping", help="check the MongoDB Atlas connection")
    commands.add_parser(
        "seed", help="load the curated catalogue into the tools collection"
    )
    idx = commands.add_parser(
        "indexes", help="create/update the Atlas Search and Vector Search indexes"
    )
    idx.add_argument(
        "--no-wait",
        action="store_true",
        help="do not wait for indexes to become queryable",
    )
    commands.add_parser("setup", help="seed the catalogue and create indexes")
    rec = commands.add_parser(
        "recommend", help="print recommendations for a brief as JSON"
    )
    rec.add_argument("brief")
    rec.add_argument("--category")
    rec.add_argument("--language", action="append", dest="languages", default=[])
    rec.add_argument(
        "--hosting", choices=["any", "self-hosted", "managed"], default="any"
    )
    rec.add_argument("--open-source-only", action="store_true")
    rec.add_argument("--max-ops", choices=["low", "medium", "high"])
    rec.add_argument("--capability", action="append", dest="capabilities", default=[])
    rec.add_argument("--limit", type=int, default=5)
    serve = commands.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    from toolhub.db import ConfigError

    try:
        sys.exit(COMMANDS[args.command](args))
    except ConfigError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    except PyMongoError as e:
        print(f"MongoDB error: {e}", file=sys.stderr)
        sys.exit(1)


def _ping(args) -> int:
    from toolhub.db import get_db, ping

    ping()
    print(f"Connected to MongoDB (database: {get_db().name})")
    return 0


def _seed(args) -> int:
    from toolhub import catalog, embeddings
    from toolhub.db import get_db

    stats = catalog.seed(get_db()["tools"], catalog.load_catalog(), embeddings.mode())
    print(f"Seeded tools: {stats}")
    return 0


def _indexes(args) -> int:
    from toolhub import embeddings, indexes
    from toolhub.db import get_db

    for action in indexes.ensure_indexes(
        get_db()["tools"], embeddings.mode(), wait=not args.no_wait
    ):
        print(action)
    return 0


def _setup(args) -> int:
    _seed(args)
    args.no_wait = False
    return _indexes(args)


def _recommend(args) -> int:
    from toolhub import embeddings
    from toolhub.constraints import Constraints
    from toolhub.db import get_db
    from toolhub.recommend import recommend

    c = Constraints.from_dict(vars(args))
    result = recommend(get_db(), args.brief, c, embeddings.mode(), limit=args.limit)
    print(json.dumps(result, indent=2, default=str))
    return 0


def _serve(args) -> int:
    import uvicorn

    uvicorn.run("toolhub.web:app", host=args.host, port=args.port)
    return 0


COMMANDS = {
    "ping": _ping,
    "seed": _seed,
    "indexes": _indexes,
    "setup": _setup,
    "recommend": _recommend,
    "serve": _serve,
}
