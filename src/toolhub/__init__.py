import argparse
import sys

from pymongo.errors import PyMongoError


def main() -> None:
    parser = argparse.ArgumentParser(prog="toolhub")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ping", help="check the MongoDB Atlas connection")
    args = parser.parse_args()

    if args.command == "ping":
        sys.exit(_ping())


def _ping() -> int:
    from toolhub.db import ConfigError, get_db, ping

    try:
        ping()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    except PyMongoError as e:
        print(f"Could not reach MongoDB: {e}", file=sys.stderr)
        return 1
    print(f"Connected to MongoDB (database: {get_db().name})")
    return 0
