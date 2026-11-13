"""Generate SPARQL for every question of a benchmark with one context setting, run it, save it.

Examples
  # baselines (every team runs these first)
  python -m sumqa.run --bench data/benchmarks/qald9plus_test.gold.jsonl --kg dbpedia2016 \
      --context ontology --budget 1000 --model ollama:qwen2.5-coder:7b --team B1
  python -m sumqa.run ... --context retrieval --budget 1000 ...
  # a summary (B1, B2)
  python -m sumqa.run ... --context summary --summary runs/B1/strong_dbpedia.json --variant strong
  # question-specific lines (B3)
  python -m sumqa.run ... --context lines --lines runs/B3/slices_qald_1000.jsonl --variant slice

Output: runs/<team>/<bench>__<variant>__<budget>__<model>.jsonl, one record per question.
Score it with sumqa.score.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import time

from .common import prefix_block, read_jsonl, write_jsonl
from .context import BM25, load_schema, ontology_context, retrieval_context, summary_context
from .llm import LLM, BudgetExceeded, extract_sparql
from .sparql import SparqlClient
from .tokens import COUNTER, count_tokens

KG_INFO = {
    "dbpedia2016": {"name": "DBpedia (2016-10 release)", "prefixes": ["dbo", "dbr", "dbp", "rdf", "rdfs", "xsd", "foaf"],
                    "endpoint_env": "DBPEDIA_ENDPOINT", "schema": "data/kg/dbpedia2016/schema_elements.jsonl",
                    "shots": "data/benchmarks/qald9plus_train.jsonl"},
    "dblp2022": {"name": "the dblp computer science bibliography KG (2022-08 release)",
                 "prefixes": ["dblp", "rdf", "rdfs", "xsd"], "endpoint_env": "DBLP_ENDPOINT",
                 "schema": "data/kg/dblp2022/schema_elements.jsonl", "shots": "data/benchmarks/dblpquad_train.jsonl"},
    "toy": {"name": "a toy KG about people, cities and films", "prefixes": ["ex", "exr", "rdf", "rdfs", "xsd"],
            "endpoint_env": "TOY_ENDPOINT", "schema": "data/toy/schema_elements.jsonl", "shots": None},
}

SYSTEM = ("You translate questions into SPARQL queries over {kg}. "
          "Use only classes and properties that appear in the schema information. "
          "Answer with a single SPARQL query in a ```sparql code block and nothing else.")

USER = """Prefixes you can use:
{prefixes}

Schema information:
{context}
{shots}
Question: {question}
Entities mentioned in the question: {entities}
SPARQL:"""


def few_shots(path: str | None, k: int) -> str:
    if not path or k == 0 or not os.path.exists(path):
        return ""
    rows = list(read_jsonl(path))
    ex = random.Random(562).sample(rows, min(k, len(rows)))
    parts = [f"Question: {r['question']}\nSPARQL:\n```sparql\n{r['sparql']}\n```" for r in ex]
    return "\nExamples (from other questions):\n" + "\n\n".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True, help="a *.gold.jsonl file")
    ap.add_argument("--kg", required=True, choices=sorted(KG_INFO))
    ap.add_argument("--context", required=True, choices=["none", "ontology", "retrieval", "summary", "lines"])
    ap.add_argument("--summary")
    ap.add_argument("--lines")
    ap.add_argument("--schema", help="schema_elements.jsonl (default per KG)")
    ap.add_argument("--budget", type=int, default=1000, help="context tokens; 0 = no limit")
    ap.add_argument("--model", required=True)
    ap.add_argument("--shots", type=int, default=3)
    ap.add_argument("--team", default="BASE")
    ap.add_argument("--variant", default=None, help="name of the setting in the results (default: --context)")
    ap.add_argument("--endpoint", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only the first N questions (for tests)")
    ap.add_argument("--price-in", type=float, default=0.0)
    ap.add_argument("--price-out", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    info = KG_INFO[a.kg]
    budget = a.budget or None
    variant = a.variant or a.context
    endpoint = a.endpoint or os.environ.get(info["endpoint_env"])
    if not endpoint:
        raise SystemExit(f"set --endpoint or ${info['endpoint_env']}")
    qs = list(read_jsonl(a.bench))[: a.limit or None]

    schema = index = fixed = per_q = None
    if a.context in ("ontology", "retrieval"):
        schema = load_schema(a.schema or info["schema"])
        if a.context == "ontology":
            fixed = ontology_context(schema, budget)
        else:
            index = BM25([e["text"] for e in schema])
    elif a.context == "summary":
        fixed = summary_context(a.summary, budget)
    elif a.context == "lines":
        from .context import cut_to_budget
        per_q = {r["id"]: cut_to_budget(r["lines"], budget) for r in read_jsonl(a.lines)}
    elif a.context == "none":
        fixed = []

    llm = LLM(a.model, price_in=a.price_in, price_out=a.price_out)
    kg = SparqlClient(endpoint)
    shots = few_shots(info["shots"], a.shots)
    bench = os.path.basename(a.bench).split(".")[0]
    model_tag = re.sub(r"[^A-Za-z0-9.]+", "-", a.model)
    out = a.out or f"runs/{a.team}/{bench}__{variant}__{a.budget}__{model_tag}.jsonl"
    rows = []
    t_start = time.time()
    for i, q in enumerate(qs):
        if fixed is not None:
            lines = fixed
        elif per_q is not None:
            lines = per_q.get(q["id"], [])
        else:
            words = q["question"] + " " + " ".join(e.rsplit("/", 1)[-1].replace("_", " ") for e in q["entities"])
            lines = retrieval_context(schema, index, words, budget)
        context = "\n".join(lines) if lines else "(none)"
        user = USER.format(prefixes=prefix_block(info["prefixes"]), context=context, shots=shots,
                           question=q["question"], entities=", ".join(f"<{e}>" for e in q["entities"]) or "(none)")
        try:
            gen = llm.generate(SYSTEM.format(kg=info["name"]), user, record=q)
        except BudgetExceeded as e:
            print(f"stopped: {e}")
            break
        sparql = extract_sparql(gen["text"])
        res = kg.query(sparql) if sparql else {"ok": False, "answers": [], "error": "no query in the answer"}
        rows.append({
            "id": q["id"], "question": q["question"], "team": a.team, "variant": variant, "context": a.context,
            "budget": a.budget, "model": a.model, "shots": a.shots, "kg": a.kg, "benchmark": bench,
            "context_lines": len(lines), "context_tokens": count_tokens(context), "token_counter": COUNTER,
            "prompt_tokens": gen.get("prompt_tokens"), "completion_tokens": gen.get("completion_tokens"),
            "llm_seconds": gen.get("seconds"), "cached": gen.get("cached"),
            "pred_sparql": sparql, "raw": gen["text"][:4000],
            "ok": res["ok"], "error": res["error"], "answers": res["answers"][:2000],
            "gold_sparql": q["sparql"], "gold_answers": q["gold_answers"],
        })
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(qs)} questions, {time.time() - t_start:.0f}s")
    write_jsonl(out, rows)
    with open(out + ".context.json", "w") as f:       # what the model saw (shared lines only)
        json.dump({"lines": fixed} if fixed is not None else {"per_question": a.context}, f)
    print(f"{len(rows)} predictions -> {out}")
    llm.close()
    kg.close()


if __name__ == "__main__":
    main()
