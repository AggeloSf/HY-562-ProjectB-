"""Shared helpers for the SumQA kit (HY562 Fall 2026, Project B).

Do not change this file in your team repository; every team is scored with it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Iterable, Iterator

PREFIXES = {
    "dbo": "http://dbpedia.org/ontology/",
    "dbr": "http://dbpedia.org/resource/",
    "dbp": "http://dbpedia.org/property/",
    "dblp": "https://dblp.org/rdf/schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "ex": "http://example.org/ontology/",
    "exr": "http://example.org/resource/",
}


def shorten(iri: str) -> str:
    for p, ns in PREFIXES.items():
        if iri.startswith(ns) and re.fullmatch(r"[A-Za-z0-9_\-.]*", iri[len(ns):] or ""):
            return f"{p}:{iri[len(ns):]}"
    return f"<{iri}>"


def prefix_block(names: Iterable[str] | None = None) -> str:
    names = names or PREFIXES.keys()
    return "\n".join(f"PREFIX {p}: <{PREFIXES[p]}>" for p in names)


def read_jsonl(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: str, rows: Iterable[dict]) -> int:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


PREFIX_DECL = re.compile(r"PREFIX\s+([A-Za-z0-9_-]*):\s*<([^>]*)>", re.I)
FULL_IRI = re.compile(r"<(https?://[^>\s]+)>")
PNAME = re.compile(r"(?<![\w<])([A-Za-z][\w-]*):([A-Za-z0-9_\-.%]*[A-Za-z0-9_%)]|\([^)\s]*\))")
RESOURCE_NS = ("http://dbpedia.org/resource/", "https://dblp.org/pid/", "https://dblp.org/rec/",
               "http://example.org/resource/")


def entities_in_query(sparql: str, resource_ns=RESOURCE_NS) -> list[str]:
    """Resource IRIs of a gold query (full IRIs and prefixed names). They are given to the
    model as oracle entity links, so that every setting uses the same entity linking."""
    prefixes = {p: ns for p, ns in PREFIX_DECL.findall(sparql)}
    for p, ns in (("dbr", PREFIXES["dbr"]), ("res", PREFIXES["dbr"]), ("exr", PREFIXES["exr"])):
        prefixes.setdefault(p, ns)
    body = PREFIX_DECL.sub(" ", sparql)
    out = []
    for iri in FULL_IRI.findall(body):
        if iri.startswith(resource_ns) and iri not in out:
            out.append(iri)
    body = FULL_IRI.sub(" ", body)
    for p, local in PNAME.findall(body):
        if p in prefixes:
            iri = prefixes[p] + local
            if iri.startswith(resource_ns) and iri not in out:
                out.append(iri)
    return out
