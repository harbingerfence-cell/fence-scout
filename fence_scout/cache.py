"""SQLite cache so re-running a scan never pays twice for the same API call."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, path: str | Path = ".cache/fence_scout.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS kv (ns TEXT, k TEXT, v TEXT, PRIMARY KEY (ns, k))")
        self.db.commit()

    def get(self, ns: str, key: str) -> Any | None:
        row = self.db.execute("SELECT v FROM kv WHERE ns=? AND k=?", (ns, key)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, ns: str, key: str, value: Any) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?,?)", (ns, key, json.dumps(value)))
        self.db.commit()


class NullCache(Cache):
    def __init__(self):
        self._d: dict = {}

    def get(self, ns, key):
        return self._d.get((ns, key))

    def set(self, ns, key, value):
        self._d[(ns, key)] = value
