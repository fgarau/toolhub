import os
from functools import cache

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.server_api import ServerApi

DEFAULT_DB_NAME = "toolhub"


class ConfigError(RuntimeError):
    pass


@cache
def get_client() -> MongoClient:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ConfigError(
            "MONGODB_URI is not set. Export your Atlas connection string first."
        )
    return MongoClient(uri, server_api=ServerApi("1"), appname="toolhub")


def get_db() -> Database:
    return get_client()[os.environ.get("MONGODB_DB", DEFAULT_DB_NAME)]


def ping() -> dict:
    return get_db().command("ping")
