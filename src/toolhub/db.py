import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()


def get_client() -> MongoClient:
    return MongoClient(os.environ["MONGODB_URI"], server_api=ServerApi("1"))


def ping() -> None:
    get_client().admin.command("ping")
    print("Connected to cluster1")


if __name__ == "__main__":
    ping()
