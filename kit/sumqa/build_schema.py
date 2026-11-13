"""Schema elements for the two baselines, from the ontology file and the KG counts.

    python -m sumqa.build_schema --ontology data/kg/dbpedia2016/raw/dbpedia_2016-10.nt \
        --counts data/kg/dbpedia2016/counts.json --out data/kg/dbpedia2016/schema_elements.jsonl

One element per class and per property:
  class dbo:Scientist "scientist" subClassOf dbo:Person
  property dbo:birthPlace "birth place" domain dbo:Person range dbo:Place
Properties that are used in the KG but not declared in the ontology (for example
the dbp: infobox properties of DBpedia) are added with their label taken from the
local name. Only classes and properties that occur in the KG are kept
(--min-count). The count is the number of instances (classes) or triples (properties).
"""
import argparse
import json
import re

import rdflib
from rdflib.namespace import OWL, RDF, RDFS

from .common import shorten, write_jsonl


def label_from_iri(iri):
    loc = re.split(r"[/#]", iri.rstrip("/#"))[-1]
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", loc).replace("_", " ").lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology", nargs="*", default=[])
    ap.add_argument("--counts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-count", type=int, default=20)
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    counts = json.load(open(a.counts))
    g = rdflib.Graph()
    for f in a.ontology:
        fmt = "nt" if f.endswith(".nt") else ("xml" if f.endswith((".owl", ".rdf")) else "turtle")
        g.parse(f, format=fmt)

    def label(x):
        best = None
        for lab in g.objects(x, RDFS.label):
            if getattr(lab, "language", None) in (a.lang, None):
                best = str(lab)
                if lab.language == a.lang:
                    break
        return best or label_from_iri(str(x))

    out, seen = [], set()
    for c, n in counts["classes"].items():
        if n < a.min_count:
            continue
        uc = rdflib.URIRef(c)
        sup = [shorten(str(s)) for s in g.objects(uc, RDFS.subClassOf) if isinstance(s, rdflib.URIRef)
               and str(s) != str(OWL.Thing)]
        text = f'class {shorten(c)} "{label(uc)}"' + (f" subClassOf {', '.join(sup[:2])}" if sup else "")
        out.append({"iri": c, "kind": "class", "text": text, "count": n})
        seen.add(c)
    for p, n in counts["properties"].items():
        if n < a.min_count or p == str(RDF.type) or p in seen:
            continue
        up = rdflib.URIRef(p)
        dom = [shorten(str(x)) for x in g.objects(up, RDFS.domain)]
        rng = [shorten(str(x)) for x in g.objects(up, RDFS.range)]
        text = f'property {shorten(p)} "{label(up)}"'
        if dom:
            text += f" domain {dom[0]}"
        if rng:
            text += f" range {rng[0]}"
        out.append({"iri": p, "kind": "property", "text": text, "count": n})
    out.sort(key=lambda e: -e["count"])
    write_jsonl(a.out, out)
    print(f"{sum(e['kind'] == 'class' for e in out)} classes, {sum(e['kind'] == 'property' for e in out)} "
          f"properties -> {a.out}")


if __name__ == "__main__":
    main()
