"""
JSON-backed mock MongoDB for local/demo when MongoDB is unavailable.
Mirrors collection names and document shapes used by localapp.views.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, List, Optional

from django.conf import settings


def _mock_data_path() -> Path:
    return Path(getattr(settings, "MOCK_MONGO_DATA_DIR", str(Path(settings.BASE_DIR) / "mock_data")))


def _load_collections() -> dict[str, list[dict]]:
    path = _mock_data_path() / "mongo_collections.json"
    if not path.is_file():
        return {
            "restapi_trainlogdata": [],
            "restapi_allbranch": [],
            "restapi_squaddetails": [],
        }
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        "restapi_trainlogdata": data.get("restapi_trainlogdata", []),
        "restapi_allbranch": data.get("restapi_allbranch", []),
        "restapi_squaddetails": data.get("restapi_squaddetails", []),
    }


def _doc_matches(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for key, cond in query.items():
        if key == "$and":
            if not all(_doc_matches(doc, sub) for sub in cond):
                return False
            continue
        if key not in doc:
            return False
        val = doc[key]
        if isinstance(cond, dict):
            if "$gte" in cond or "$lte" in cond:
                lo = cond.get("$gte")
                hi = cond.get("$lte")
                if lo is not None and val < lo:
                    return False
                if hi is not None and val > hi:
                    return False
            elif "$regex" in cond:
                pat = cond["$regex"]
                if isinstance(pat, re.Pattern):
                    if not pat.search(str(val)):
                        return False
                else:
                    if not re.search(str(pat), str(val)):
                        return False
            else:
                if val != cond:
                    return False
        else:
            if val != cond:
                return False
    return True


class MockCursor:
    def __init__(self, docs: List[dict], query: dict):
        self._docs = [d for d in docs if _doc_matches(d, query)]
        self._sort_key: Optional[str] = None
        self._sort_dir = 1

    def sort(self, key: str, direction: int = 1) -> "MockCursor":
        self._sort_key = key
        self._sort_dir = direction
        return self

    def __iter__(self) -> Iterator[dict]:
        rows = deepcopy(self._docs)
        if self._sort_key:
            rows.sort(key=lambda x: x.get(self._sort_key, ""), reverse=self._sort_dir < 0)
        yield from rows


class MockCollection:
    def __init__(self, name: str, store: dict[str, list[dict]]):
        self._name = name
        self._store = store

    def find(self, query: Optional[dict] = None) -> MockCursor:
        docs = self._store.get(self._name, [])
        return MockCursor(docs, query or {})

    def aggregate(self, pipeline: list[dict]) -> list[dict]:
        docs = deepcopy(self._store.get(self._name, []))
        out: list[dict] = list(docs)
        for stage in pipeline:
            if "$group" in stage:
                grp = stage["$group"]
                _id_field = grp["_id"]
                key_name = _id_field.replace("$", "")
                counts: dict[Any, int] = {}
                for d in out:
                    k = d.get(key_name)
                    counts[k] = counts.get(k, 0) + 1
                out = [{"_id": k, "count": v} for k, v in counts.items()]
            elif "$count" in stage:
                field = stage["$count"]
                return [{field: len(out)}]
        return out


class MockDatabase:
    def __init__(self):
        self._collections = _load_collections()

    def __getitem__(self, name: str) -> MockCollection:
        return MockCollection(name, self._collections)


def get_mongo_database():
    """
    Returns a pymongo Database or MockDatabase based on USE_MOCK_MONGO.
    Both support db[collection].find().sort() and .aggregate() as used in views.
    """
    if getattr(settings, "USE_MOCK_MONGO", False):
        return MockDatabase()
    from pymongo import MongoClient

    client = MongoClient(
        settings.DATABASES["default"]["CLIENT"]["host"],
        settings.DATABASES["default"]["CLIENT"]["port"],
    )
    return client[settings.DATABASES["default"]["NAME"]]
