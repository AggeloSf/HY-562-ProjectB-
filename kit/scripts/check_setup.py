"""Check that the Project B set-up is complete and write SETUP_REPORT.txt (commit it to your repository).

    python scripts/check_setup.py
Uses $DBPEDIA_ENDPOINT, $DBLP_ENDPOINT and $OLLAMA_HOST (see SETUP.md).
"""
import json
import os
import platform
import sys

import requests

sys.path.insert(0, os.getcwd())
lines, ok_all = [], True


def check(name, ok, detail=""):
    global ok_all
    ok_all &= bool(ok)
    lines.append(f"[{'OK ' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))


def count(path):
    return sum(1 for _ in open(path)) if os.path.exists(path) else 0


lines.append(f"python {platform.python_version()} on {platform.platform()}")
for mod in ("rdflib", "pyoxigraph", "tiktoken", "pyspark"):
    try:
        m = __import__(mod)
        check(f"module {mod}", True, getattr(m, "__version__", ""))
    except Exception as e:
        check(f"module {mod}", mod == "tiktoken", f"{e}" + (" (optional)" if mod == "tiktoken" else ""))

from sumqa.sparql import SparqlClient  # noqa: E402

for kg, env, probe in (("dbpedia2016", "DBPEDIA_ENDPOINT", "ASK { <http://dbpedia.org/resource/Heraklion> ?p ?o }"),
                       ("dblp2022", "DBLP_ENDPOINT", "ASK { ?s a <https://dblp.org/rdf/schema#Publication> }")):
    ep = os.environ.get(env)
    if not ep:
        check(f"{kg} endpoint", False, f"${env} is not set")
        continue
    cli = SparqlClient(ep, cache_dir="cache/check")
    r = cli.query(probe)
    check(f"{kg} endpoint {ep}", r["ok"] and r["answers"] == ["true"], r["error"] or f"probe answered {r['answers']}")
    cli.close()
    sch = f"data/kg/{kg}/schema_elements.jsonl"
    check(f"{kg} schema elements", count(sch) > 50, f"{count(sch)} elements")

for b in ("qald9plus_test", "lcquad1_test", "dblpquad_test"):
    n = count(f"data/benchmarks/{b}.gold.jsonl")
    check(f"gold answers {b}", n > 0, f"{n} questions kept ({count(f'data/benchmarks/{b}.dropped.jsonl')} dropped)")

host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
try:
    tags = requests.get(f"{host}/api/tags", timeout=5).json()
    names = [m["name"] for m in tags.get("models", [])]
    check("Ollama reachable", True, host)
    check("model qwen2.5-coder:7b pulled", any(n.startswith("qwen2.5-coder:7b") for n in names), ", ".join(names))
except Exception as e:
    check("Ollama reachable", False, f"{host}: {e}")

lines.append("ALL CHECKS PASSED" if ok_all else "SOME CHECKS FAILED")
open("SETUP_REPORT.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
