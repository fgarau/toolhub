"""Embedding modes.

``auto`` (default) uses Atlas Automated Embedding: Atlas embeds ``search_text``
at index time and the brief at query time with a Voyage AI model.

``hash`` is a dependency-free, offline fallback for local development (e.g. the
``mongodb-atlas-local`` image without a Voyage API key). It hashes word
unigrams/bigrams into a fixed-size vector, so it is lexical, not semantic.
"""

import hashlib
import itertools
import math
import os
import re

AUTO = "auto"
HASH = "hash"
MODES = (AUTO, HASH)
HASH_DIMENSIONS = 256
DEFAULT_MODEL = "voyage-4"


def mode() -> str:
    value = os.environ.get("TOOLHUB_EMBEDDINGS", AUTO)
    if value not in MODES:
        raise ValueError(f"TOOLHUB_EMBEDDINGS must be one of {MODES}, got {value!r}")
    return value


def model() -> str:
    return os.environ.get("TOOLHUB_EMBED_MODEL", DEFAULT_MODEL)


def hash_embed(text: str, dimensions: int = HASH_DIMENSIONS) -> list[float]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    features = words + [f"{a} {b}" for a, b in itertools.pairwise(words)]
    vector = [0.0] * dimensions
    for feature in features:
        digest = hashlib.md5(feature.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % dimensions
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
