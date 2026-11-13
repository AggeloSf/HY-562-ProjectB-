"""Score a run and append one row to the shared results table.

    python -m sumqa.score runs/B1/qald9plus_test__strong__1000__ollama-qwen2.5-coder-7b.jsonl \
        --results results/results_B.csv

Per question: precision, recall and F1 of the answer set against the gold answers
(QALD style; for ASK queries the answer set is {"true"} or {"false"}), and one outcome:
  no_query      no SPARQL in the model output
  error         the query fails (syntax error, unknown prefix, timeout)
  empty         the query runs and returns nothing
  wrong         answers returned, F1 = 0
  partial       0 < F1 < 1
  correct       F1 = 1
Run level: execution accuracy (share of correct), macro precision/recall/F1,
mean context and prompt tokens, and the outcome counts.
--errors writes the non-correct questions to a CSV with empty columns for the
manual error taxonomy (wrong_property, wrong_direction, missing_join,
hallucinated_iri, wrong_class, other).
"""
import argparse
import csv
import os
from collections import Counter

from .common import read_jsonl


def prf(pred, gold):
    p, g = set(pred), set(gold)
    if not p and not g:
        return 1.0, 1.0, 1.0
    tp = len(p & g)
    pr = tp / len(p) if p else 0.0
    rc = tp / len(g) if g else 0.0
    return pr, rc, (2 * pr * rc / (pr + rc) if pr + rc else 0.0)


def outcome(r, f1):
    if not r["pred_sparql"]:
        return "no_query"
    if not r["ok"]:
        return "error"
    if not r["answers"]:
        return "empty"
    if f1 == 1.0:
        return "correct"
    return "partial" if f1 > 0 else "wrong"


def score(rows):
    per = []
    for r in rows:
        p, rc, f = prf(r["answers"], r["gold_answers"]) if r["ok"] else (0.0, 0.0, 0.0)
        per.append({**r, "precision": p, "recall": rc, "f1": f, "outcome": outcome(r, f)})
    n = len(per)
    oc = Counter(x["outcome"] for x in per)

    def mean(key):
        vals = [x[key] for x in per if x.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    first = per[0] if per else {}
    summary = {k: first.get(k) for k in ("team", "variant", "context", "benchmark", "kg", "budget", "model", "shots",
                                         "token_counter")}
    summary.update({"n": n, "accuracy": round(oc["correct"] / n, 4) if n else None,
                    "macro_precision": mean("precision"), "macro_recall": mean("recall"), "macro_f1": mean("f1"),
                    "mean_context_tokens": mean("context_tokens"), "mean_prompt_tokens": mean("prompt_tokens"),
                    **{f"n_{k}": oc[k] for k in ("correct", "partial", "wrong", "empty", "error", "no_query")}})
    return summary, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--results")
    ap.add_argument("--errors", help="CSV for the manual error taxonomy")
    a = ap.parse_args()
    summary, per = score(list(read_jsonl(a.run)))
    for k, v in summary.items():
        print(f"{k:>20}: {v}")
    if a.results:
        new = not os.path.exists(a.results)
        os.makedirs(os.path.dirname(a.results) or ".", exist_ok=True)
        with open(a.results, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary))
            if new:
                w.writeheader()
            w.writerow(summary)
        print(f"appended to {a.results}")
    if a.errors:
        cols = ["id", "outcome", "f1", "question", "pred_sparql", "gold_sparql", "error",
                "wrong_property", "wrong_direction", "missing_join", "hallucinated_iri", "wrong_class", "other", "note"]
        with open(a.errors, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for x in per:
                if x["outcome"] != "correct":
                    w.writerow({**x, "f1": round(x["f1"], 3)})
        print(f"error sheet -> {a.errors}")


if __name__ == "__main__":
    main()
