"""SPARQL access with a disk cache.

Endpoints:
  oxigraph:DIR       a local Oxigraph store built with `python -m sumqa.kgstore` (the default set-up)
  http(s)://...      any SPARQL endpoint (for example your own QLever, or a public one for quick tests)
  file:path.nt       a local file loaded with rdflib (toy data and small tests only)

Results are normalised to a set of strings (all values of all variables), which is
what the scorer compares; ASK queries give {"true"} or {"false"}.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import requests

from .cache import DiskCache
from .common import sha


class QueryError(Exception):
    pass


class SparqlClient:
    def __init__(self, endpoint: str, cache_dir: str = "cache/sparql", timeout: float = 30.0,
                 access_token: str | None = None):
        self.endpoint = endpoint
        self.timeout = timeout
        self.token = access_token or os.environ.get("SUMQA_SPARQL_TOKEN")
        os.makedirs(cache_dir, exist_ok=True)
        self._cache = DiskCache(os.path.join(cache_dir, sha(endpoint) + ".sqlite"))
        self._graph = None
        self._store = None
        self._glock = threading.Lock()      # rdflib's SPARQL parser is not thread-safe
        if endpoint.startswith("oxigraph:"):
            import pyoxigraph as ox
            self._store = ox.Store.read_only(endpoint[len("oxigraph:"):])
        elif endpoint.startswith("file:"):
            import rdflib
            self._graph = rdflib.Graph()
            self._graph.parse(endpoint[5:], format="nt")

    def close(self):
        self._cache.close()

    def query(self, sparql: str) -> dict:
        """Returns {"ok": bool, "answers": [..], "error": str|None, "seconds": float}."""
        key = sha(sparql)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        t0 = time.time()
        try:
            answers = self._run(sparql)
            res = {"ok": True, "answers": sorted(answers), "error": None}
        except QueryError as e:
            res = {"ok": False, "answers": [], "error": str(e)[:500]}
        res["seconds"] = round(time.time() - t0, 3)
        if res["ok"] or "timeout" not in (res["error"] or "").lower():
            self._cache.put(key, res)
        return res

    def _run(self, sparql: str) -> set[str]:
        if self._store is not None:
            try:
                worker = subprocess.run(
                    [sys.executable, os.path.join(os.path.dirname(__file__), "oxigraph_query.py")],
                    input=json.dumps({"store": self.endpoint[len("oxigraph:"):], "query": sparql}),
                    text=True, capture_output=True, timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                raise QueryError(f"timeout after {self.timeout:g}s") from None
            if worker.returncode:
                raise QueryError(worker.stderr.strip() or f"query worker exited {worker.returncode}")
            result = json.loads(worker.stdout)
            if "error" in result:
                raise QueryError(result["error"])
            return set(result["answers"])
        if self._graph is not None:
            try:
                with self._glock:
                    r = self._graph.query(sparql)
                    rows = list(r) if r.type != "ASK" else None
            except Exception as e:  # syntax errors and the like
                raise QueryError(f"{type(e).__name__}: {e}")
            if r.type == "ASK":
                return {"true" if r.askAnswer else "false"}
            return {str(v) for row in rows for v in row if v is not None}
        headers = {"Accept": "application/sparql-results+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            resp = requests.post(self.endpoint, data={"query": sparql}, headers=headers, timeout=self.timeout)
        except requests.Timeout:
            raise QueryError("timeout")
        except requests.RequestException as e:
            raise QueryError(f"connection: {e}")
        if resp.status_code in (405, 415):      # endpoints that only accept GET
            try:
                resp = requests.get(self.endpoint, params={"query": sparql}, headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                raise QueryError(f"connection: {e}")
        if resp.status_code != 200:
            raise QueryError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            js = resp.json()
        except json.JSONDecodeError:
            raise QueryError("response is not SPARQL JSON")
        if "boolean" in js:
            return {"true" if js["boolean"] else "false"}
        return {b["value"] for row in js.get("results", {}).get("bindings", []) for b in row.values()}
