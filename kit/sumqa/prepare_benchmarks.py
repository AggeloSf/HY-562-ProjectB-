"""Convert the benchmark files to one JSON-lines format.

    python -m sumqa.prepare_benchmarks --raw data/benchmarks/raw --out data/benchmarks

Input (downloaded by scripts/download_benchmarks.sh):
  qald_9_plus_{train,test}_dbpedia.json   QALD-9-plus, DBpedia part (CC BY 4.0)
  lcquad1_{train,test}.json               LC-QuAD 1.0 (GPL-3.0)
  dblp_quad/{train,valid,test}.json       DBLP-QuAD (CC BY 4.0), exported from Hugging Face
Output, one file per benchmark and split:
  {"id", "benchmark", "kg", "question", "sparql", "entities"}
"entities" are the resource IRIs of the gold query (oracle entity links, see README).
"""
import argparse
import json
import os
import random

from .common import entities_in_query, write_jsonl


def qald(path, name="qald9plus"):
    d = json.load(open(path, encoding="utf-8"))
    for q in d["questions"]:
        en = [x["string"] for x in q["question"] if x.get("language") == "en" and x.get("string")]
        sparql = q.get("query", {}).get("sparql")
        if not en or not sparql:
            continue
        yield {"id": f"{name}-{q['id']}", "benchmark": name, "kg": "dbpedia2016",
               "question": en[0], "sparql": sparql.strip(), "entities": entities_in_query(sparql)}


def lcquad1(path, name="lcquad1"):
    for q in json.load(open(path, encoding="utf-8")):
        text = (q.get("corrected_question") or "").strip()
        if not text or text.lower() in ("n/a", "na"):
            continue
        sparql = q["sparql_query"].strip()
        yield {"id": f"{name}-{q['_id']}", "benchmark": name, "kg": "dbpedia2016",
               "question": text, "sparql": sparql, "entities": entities_in_query(sparql)}


def _get(obj, *keys):
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return None
    return obj


def dblpquad(path, name="dblpquad"):
    d = json.load(open(path, encoding="utf-8"))
    rows = d.get("questions", d) if isinstance(d, dict) else d
    for q in rows:
        text = _get(q, "question", "string") or q.get("question")
        sparql = _get(q, "query", "sparql") or q.get("sparql") or q.get("query")
        if not isinstance(text, str) or not isinstance(sparql, str):
            continue
        yield {"id": f"{name}-{q.get('id')}", "benchmark": name, "kg": "dblp2022",
               "question": text, "sparql": sparql.strip(), "entities": entities_in_query(sparql)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/benchmarks/raw")
    ap.add_argument("--out", default="data/benchmarks")
    ap.add_argument("--lcquad-test-sample", type=int, default=300,
                    help="LC-QuAD 1.0 test has 1,000 questions; a fixed random sample keeps runs short")
    ap.add_argument("--dblp-test-sample", type=int, default=300,
                    help="DBLP-QuAD test has 2,000 questions; a fixed random sample keeps runs short")
    a = ap.parse_args()
    jobs = [
        ("qald9plus_train", qald, "qald_9_plus_train_dbpedia.json"),
        ("qald9plus_test", qald, "qald_9_plus_test_dbpedia.json"),
        ("lcquad1_train", lcquad1, "lcquad1_train.json"),
        ("lcquad1_test", lcquad1, "lcquad1_test.json"),
        ("dblpquad_train", dblpquad, "dblp_quad/train.json"),
        ("dblpquad_test", dblpquad, "dblp_quad/test.json"),
    ]
    for out_name, fn, src in jobs:
        path = os.path.join(a.raw, src)
        if not os.path.exists(path):
            print(f"skip {out_name}: {path} not found")
            continue
        rows = list(fn(path))
        cap = {"dblpquad_test": a.dblp_test_sample, "lcquad1_test": a.lcquad_test_sample}.get(out_name)
        if cap and len(rows) > cap:
            rows = random.Random(562).sample(rows, cap)
        n = write_jsonl(os.path.join(a.out, f"{out_name}.jsonl"), rows)
        print(f"{out_name}: {n} questions")


if __name__ == "__main__":
    main()
