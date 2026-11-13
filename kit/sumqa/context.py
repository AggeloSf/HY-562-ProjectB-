"""Schema context for the prompt: the common baselines and the summary serializer.

A context is a list of lines. Every setting (baseline or team variant) produces,
for each question, a list of lines that is cut to a token budget. The kit has
three providers:

  ontology   schema elements (classes, properties) ordered by how often they are
             used in the KG, cut to the budget. Same lines for every question.
  retrieval  schema elements ranked by BM25 against the question, cut to the budget.
  summary    a summary file (format below) serialised to lines, edges ordered by
             count, cut to the budget. Same lines for every question.
Teams with question-specific contexts (for example slices) write their own lines
per question into a JSON-lines file {"id": question id, "lines": [...]} and use
the "lines" provider of run.py.

Summary file format (JSON), written by the teams' PySpark code:
{
  "kg": "dbpedia2016", "kind": "strong", "team": "B1",
  "nodes": [{"id": "n1", "classes": ["http://dbpedia.org/ontology/Person"], "size": 1234,
             "properties": ["http://dbpedia.org/ontology/birthDate", ...]}],     # optional
  "edges": [{"source": "n1", "property": "http://dbpedia.org/ontology/birthPlace",
             "target": "n2", "count": 4567}],
  "attributes": [{"node": "n1", "property": "http://dbpedia.org/ontology/birthDate",
                  "datatype": "http://www.w3.org/2001/XMLSchema#date", "count": 900}]   # optional
}
A node without classes is described by its properties (as in weak and strong summaries).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from .common import read_jsonl, shorten
from .tokens import count_tokens


# ---------------------------------------------------------------- budget cut
def cut_to_budget(lines: list[str], budget: int | None) -> list[str]:
    if budget is None:
        return list(lines)
    out, used = [], 0
    for ln in lines:
        t = count_tokens(ln) + 1
        if used + t > budget:
            break
        out.append(ln)
        used += t
    return out


# ---------------------------------------------------------------- schema elements
def load_schema(path: str) -> list[dict]:
    """schema_elements.jsonl written by sumqa.build_schema: {"iri", "kind", "text", "count"}."""
    return sorted(read_jsonl(path), key=lambda e: -e.get("count", 0))


def ontology_context(schema: list[dict], budget: int | None) -> list[str]:
    return cut_to_budget([e["text"] for e in schema], budget)


_tok = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    # split camelCase so that "birthPlace" matches "birth place"
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return _tok.findall(text.lower())


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.2, b: float = 0.75):
        self.docs = [_words(d) for d in docs]
        self.avg = sum(map(len, self.docs)) / max(1, len(self.docs))
        df = Counter(w for d in self.docs for w in set(d))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = _words(query)
        out = []
        for d, tf in zip(self.docs, self.tf):
            s = 0.0
            for w in q:
                if w in tf:
                    f = tf[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            out.append(s)
        return out


def retrieval_context(schema: list[dict], index: BM25, question: str, budget: int | None) -> list[str]:
    sc = index.scores(question)
    order = sorted(range(len(schema)), key=lambda i: (-sc[i], -schema[i].get("count", 0)))
    return cut_to_budget([schema[i]["text"] for i in order], budget)


# ---------------------------------------------------------------- summaries
def summary_lines(summary: dict) -> list[str]:
    """Serialise a summary: edges ordered by count; a node's description line comes
    right before the first edge that uses it, so any prefix of the list is self-contained."""
    nodes = {n["id"]: n for n in summary.get("nodes", [])}
    attrs = {}
    for a in summary.get("attributes", []):
        attrs.setdefault(a["node"], []).append(a)

    def node_line(nid):
        n = nodes.get(nid, {"id": nid})
        if n.get("classes"):
            desc = ", ".join(shorten(c) for c in n["classes"][:6])
        else:
            props = n.get("properties", [])[:6]
            desc = "untyped; has " + ", ".join(shorten(p) for p in props) if props else "untyped"
        size = f" ({n['size']} entities)" if n.get("size") is not None else ""
        extra = ""
        if attrs.get(nid):
            top = sorted(attrs[nid], key=lambda a: -a.get("count", 0))[:8]
            extra = "; literals: " + ", ".join(f"{shorten(a['property'])}:{shorten(a['datatype'])}" for a in top)
        return f"{nid} = [{desc}]{size}{extra}"

    out, seen = [], set()
    for e in sorted(summary.get("edges", []), key=lambda e: -e.get("count", 0)):
        for nid in (e["source"], e["target"]):
            if nid not in seen:
                out.append(node_line(nid))
                seen.add(nid)
        out.append(f"{e['source']} {shorten(e['property'])} {e['target']} ({e.get('count', '?')})")
    for nid in nodes:                          # nodes without edges, at the end
        if nid not in seen:
            out.append(node_line(nid))
    return out


def summary_context(summary_path: str, budget: int | None) -> list[str]:
    with open(summary_path, encoding="utf-8") as f:
        return cut_to_budget(summary_lines(json.load(f)), budget)
