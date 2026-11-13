"""Run the gold queries on the endpoint and keep the questions that work.

    python -m sumqa.gold --bench data/benchmarks/qald9plus_test.jsonl --endpoint $DBPEDIA_ENDPOINT

The gold answers are recomputed on the course endpoint, so that gold and predicted
queries run on exactly the same KG version. Questions whose gold query fails or
returns nothing are dropped and listed in <bench>.dropped.jsonl.
Output: <bench without .jsonl>.gold.jsonl with an extra field "gold_answers".
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

from .common import read_jsonl, write_jsonl
from .sparql import SparqlClient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()
    cli = SparqlClient(a.endpoint, timeout=a.timeout)
    qs = list(read_jsonl(a.bench))
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda q: cli.query(q["sparql"]), qs))
    keep, drop = [], []
    for q, r in zip(qs, res):
        if r["ok"] and r["answers"]:
            keep.append({**q, "gold_answers": r["answers"]})
        else:
            drop.append({**q, "reason": r["error"] or "empty result"})
    base = a.bench[:-len(".jsonl")]
    write_jsonl(base + ".gold.jsonl", keep)
    write_jsonl(base + ".dropped.jsonl", drop)
    print(f"{len(keep)} kept, {len(drop)} dropped -> {base}.gold.jsonl")
    cli.close()


if __name__ == "__main__":
    main()
