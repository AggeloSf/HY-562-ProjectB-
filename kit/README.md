# Project B kit: SumQA

HY562 / CS-562 Fall 2026. Everything every Project B team needs: benchmarks, scripts that build local KG stores,
the two baselines, the LLM runner, the scorer and the ablation script. Each team sets everything up itself:
start with `SETUP.md`. All teams use this kit unchanged, so that results
can be compared. The project description is `../CS562_ProjectB_2026.pdf`.

## Contents

| Path | What it is |
|---|---|
| `ProjectB_starter.ipynb` | Starter notebook: toy pipeline end to end, where your summary code goes |
| `sumqa/prepare_benchmarks.py` | Benchmarks to one JSON-lines format, with oracle entity links |
| `sumqa/gold.py` | Runs the gold queries on the course endpoint; keeps the questions that work |
| `sumqa/kgstats.py` | (PySpark) class and property counts; converts a KG to Parquet |
| `sumqa/build_schema.py` | Schema elements (classes, properties) for the baselines |
| `sumqa/context.py` | Baselines (ontology, retrieval) and the summary serializer; summary file format |
| `sumqa/run.py` | Prompt, LLM call, query execution, one record per question |
| `sumqa/score.py` | Accuracy, macro F1, outcome counts, error sheet for the manual taxonomy |
| `sumqa/ablation.py` | Counterfactual ablation of context lines (RQ3) |
| `sumqa/llm.py`, `sumqa/sparql.py`, `sumqa/cache.py` | Ollama / OpenAI-compatible / mock models, SPARQL client, disk caches |
| `scripts/make_toy.py` | Toy KG, ontology and 12 questions (runs without a server) |
| `scripts/download_benchmarks.sh` | Adds DBLP-QuAD from Hugging Face and converts all benchmarks |
| `scripts/download_kgs.sh` | DBpedia 2016-10 and dblp 2022-08 dumps (for summaries) |
| `sumqa/kgstore.py` | Loads a KG into a local Oxigraph store (SPARQL without a server) |
| `scripts/check_setup.py` | Checks the set-up and writes `SETUP_REPORT.txt` |
| `qlever/Qleverfile.*` | Optional QLever configurations, if a team wants a faster endpoint |
| `data/benchmarks/` | QALD-9-plus and LC-QuAD 1.0 files, already converted |

## Quick start (toy KG, no server, no model)

```bash
export TOY_ENDPOINT=file:data/toy/kg.nt
python scripts/make_toy.py
python -m sumqa.gold --bench data/toy/toy_test.jsonl --endpoint $TOY_ENDPOINT
python -m sumqa.run --bench data/toy/toy_test.gold.jsonl --kg toy --context retrieval --budget 150 --model mock:noisy --team B1
python -m sumqa.score runs/B1/toy_test__retrieval__150__mock-noisy.jsonl
```

## Benchmarks and knowledge graphs

| KG | Version | Size | Benchmarks (questions used) | Source and license |
|---|---|---|---|---|
| DBpedia | 2016-10, English core files + ontology | about 1.1 GB compressed | QALD-9-plus DBpedia (150 test, 408 train), LC-QuAD 1.0 (300 sampled from the 1,000 test questions, 4,000 train) | [downloads.dbpedia.org/2016-10](https://downloads.dbpedia.org/2016-10/core-i18n/en/), CC BY-SA 3.0; [QALD-9-plus](https://github.com/KGQA/QALD_9_plus) CC BY 4.0; [LC-QuAD](https://github.com/AskNowQA/LC-QuAD) GPL-3.0 |
| dblp | RDF dump of 2022-08-01 | 2.8 GB compressed | DBLP-QuAD (300 sampled from the 2,000 test questions, 7,000 train) | [Zenodo 10.5281/zenodo.7638511](https://zenodo.org/records/7638511), CC BY 4.0; [DBLP-QuAD](https://huggingface.co/datasets/awalesushil/DBLP-QuAD) CC BY 4.0 |

Notes:
- LC-QuAD 1.0 was written for DBpedia 2016-04 and uses many `dbp:` infobox properties; that is why the
  DBpedia endpoint also loads `infobox_properties_en`. Gold answers are recomputed on our endpoint
  (`sumqa.gold`), and questions whose gold query fails or returns nothing are dropped and listed.
- Entity linking is not part of this project. Every setting gets the resource IRIs of the gold query
  ("oracle entity links"), so the comparison isolates the effect of the schema context.

## Endpoints and models

Each team loads both KGs into local Oxigraph stores (`sumqa.kgstore`, see `SETUP.md`) and sets:
```bash
export DBPEDIA_ENDPOINT=oxigraph:data/kg/dbpedia2016/store
export DBLP_ENDPOINT=oxigraph:data/kg/dblp2022/store
```
For development only you can use the public QLever endpoints (https://qlever.dev/api/dbpedia and
https://qlever.dev/api/dblp); they serve newer KG versions, so never report numbers from them.

Models, through [Ollama](https://ollama.com) on your laptop (16 GB RAM is enough for 7 to 9 B models):
`ollama pull qwen2.5-coder:7b` (4.7 GB) as the common model, `llama3.1:8b` (4.9 GB) or `qwen3:8b` (5.2 GB)
as the second one. How the container reaches Ollama is in `SETUP.md`, step 6.
The kit can also call an OpenAI-compatible API (`--model openai:<name>`, with `SUMQA_MAX_USD` as a spending
cap), but the required runs use local models only.

## Settings, budgets and the results table

- Context providers: `none`, `ontology`, `retrieval` (the two baselines every team runs), `summary`
  (a summary file), `lines` (your own lines per question).
- Budgets: 500, 1000 and 2000 context tokens (`--budget`), counted with tiktoken `cl100k_base`
  (`pip install tiktoken`; without it the kit counts characters / 4 and says so in the results).
- Prompt: fixed system message, prefixes, the context, 3 fixed examples from the training split
  (`--shots 3`), the question and the entity IRIs. Temperature 0. Do not change the prompt in your runs;
  if you want to study prompt variants, add them as a separate, clearly named experiment.
- Every scored run appends one row to `results/results_B.csv`; commit it, the tables of the teams are merged at the end.

## Summary file format

See the docstring of `sumqa/context.py`. Nodes (with classes, or with properties for untyped nodes), edges
`(source, property, target, count)` and optional literal attributes. The serializer orders edges by count
and puts each node description right before its first edge, so any prefix of the lines is self-contained.
