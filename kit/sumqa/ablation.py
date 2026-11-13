"""Counterfactual ablation (RQ3): which context lines does the model need?

    python -m sumqa.ablation --run runs/B1/qald9plus_test__strong__1000__ollama-qwen2.5-coder-7b.jsonl \
        --bench data/benchmarks/qald9plus_test.gold.jsonl --kg dbpedia2016 \
        --summary runs/B1/strong_dbpedia.json --questions 40

For each of N questions that the run answered correctly, the context is split into
at most --blocks blocks of consecutive lines; each block is removed in turn, the
query is generated again and executed. A block is NECESSARY for a question when
its removal turns the correct answer into a non-correct one.
Output (<run>.ablation.jsonl): one record per (question, block) with the removed
lines and the outcome, and a summary with
  necessity_rate      share of blocks that are necessary
  necessary_tokens    share of context tokens that sit in necessary blocks
  questions_robust    share of questions with no necessary block
The same --context, --summary/--lines, --budget, --model and --shots as the run must be given.
"""
import argparse
import json
import random

from .common import prefix_block, read_jsonl, write_jsonl
from .context import BM25, cut_to_budget, load_schema, ontology_context, retrieval_context, summary_context
from .llm import LLM, extract_sparql
from .run import KG_INFO, SYSTEM, USER, few_shots
from .score import prf
from .sparql import SparqlClient
from .tokens import count_tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--kg", required=True)
    ap.add_argument("--summary")
    ap.add_argument("--lines")
    ap.add_argument("--schema")
    ap.add_argument("--questions", type=int, default=40)
    ap.add_argument("--blocks", type=int, default=12)
    ap.add_argument("--endpoint")
    a = ap.parse_args()

    import os
    run = list(read_jsonl(a.run))
    first = run[0]
    info = KG_INFO[a.kg]
    budget = first["budget"] or None
    qmap = {q["id"]: q for q in read_jsonl(a.bench)}
    llm = LLM(first["model"])
    kg = SparqlClient(a.endpoint or os.environ.get(info["endpoint_env"]))
    shots = few_shots(info["shots"], first["shots"])
    schema = index = per_q = None
    if first["context"] in ("ontology", "retrieval"):
        schema = load_schema(a.schema or info["schema"])
        index = BM25([e["text"] for e in schema])
    if first["context"] == "lines":
        per_q = {r["id"]: cut_to_budget(r["lines"], budget) for r in read_jsonl(a.lines)}

    def lines_for(q):
        c = first["context"]
        if c == "ontology":
            return ontology_context(schema, budget)
        if c == "retrieval":
            words = q["question"] + " " + " ".join(e.rsplit("/", 1)[-1].replace("_", " ") for e in q["entities"])
            return retrieval_context(schema, index, words, budget)
        if c == "summary":
            return summary_context(a.summary, budget)
        if c == "lines":
            return per_q.get(q["id"], [])
        return []

    correct = [r for r in run if r["ok"] and prf(r["answers"], r["gold_answers"])[2] == 1.0]
    sample = random.Random(562).sample(correct, min(a.questions, len(correct)))
    out, stats = [], []
    for r in sample:
        q = qmap[r["id"]]
        lines = lines_for(q)
        if not lines:
            continue
        size = max(1, -(-len(lines) // a.blocks))
        blocks = [list(range(i, min(i + size, len(lines)))) for i in range(0, len(lines), size)]
        total_tok = sum(count_tokens(x) for x in lines)
        nec_tok, nec_blocks = 0, 0
        for b, idx in enumerate(blocks):
            kept = [ln for i, ln in enumerate(lines) if i not in set(idx)]
            user = USER.format(prefixes=prefix_block(info["prefixes"]), context="\n".join(kept) or "(none)",
                               shots=shots, question=q["question"],
                               entities=", ".join(f"<{e}>" for e in q["entities"]) or "(none)")
            gen = llm.generate(SYSTEM.format(kg=info["name"]), user, record=q)
            sp = extract_sparql(gen["text"])
            res = kg.query(sp) if sp else {"ok": False, "answers": []}
            f1 = prf(res["answers"], q["gold_answers"])[2] if res["ok"] else 0.0
            necessary = f1 < 1.0
            tok = sum(count_tokens(lines[i]) for i in idx)
            nec_tok += tok if necessary else 0
            nec_blocks += necessary
            out.append({"id": q["id"], "block": b, "removed": [lines[i] for i in idx], "tokens": tok,
                        "f1_after": round(f1, 4), "necessary": necessary, "pred_sparql": sp})
        stats.append((nec_blocks / len(blocks), nec_tok / total_tok if total_tok else 0, nec_blocks == 0))
    write_jsonl(a.run + ".ablation.jsonl", out)
    if stats:
        summary = {"questions": len(stats),
                   "necessity_rate": round(sum(s[0] for s in stats) / len(stats), 4),
                   "necessary_tokens": round(sum(s[1] for s in stats) / len(stats), 4),
                   "questions_robust": round(sum(s[2] for s in stats) / len(stats), 4)}
        with open(a.run + ".ablation.summary.json", "w") as f:
            json.dump(summary, f, indent=1)
        print(summary)
    llm.close()
    kg.close()


if __name__ == "__main__":
    main()
