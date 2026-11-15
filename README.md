# HY-562 Project B: SumQA

Course project comparing schema context methods for LLM-generated SPARQL queries.
The assignment is in `CS562_ProjectB_2026.pdf`; the supplied pipeline and setup
instructions are in `kit/`.

## Run the environment

From the repository root:

```powershell
docker compose -f 04_Environment/04_Environment/docker-compose.yml up -d
docker exec -w /home/jovyan/work/kit hy562-spark-lab python -m pip install -r requirements.txt
```

Open http://localhost:8888/lab?token=hy562 and work in `kit/`. Reinstall the
requirements after recreating the container. The Compose mount includes the whole
repository. The course Dockerfile builds Spark 4.2.0 with Java 17 and JupyterLab.

This machine uses Ollama on port **11435**, with project models in `kit/cache/ollama`.
To restart it from PowerShell in the repository root:

```powershell
New-Item -ItemType Directory -Force kit/cache/ollama | Out-Null
$env:OLLAMA_MODELS = (Resolve-Path kit/cache/ollama).Path
$env:OLLAMA_HOST = '0.0.0.0:11435'
ollama serve
```

The container uses `http://host.docker.internal:11435`. Teammates using Ollama's
default port should change `OLLAMA_HOST` in Compose to port 11434 before starting
the container. Follow `kit/SETUP.md` to download models and prepare the graphs.

## Verified progress (15 November 2026)

- Course container and JupyterLab start successfully.
- Project requirements are installed in the container; Spark version is 4.2.0.
- `qwen2.5-coder:7b` is downloaded and reachable from the container.
- The toy `mock:gold` run answers all 12 questions correctly (accuracy and F1: 1.0).
- `ProjectB_starter.ipynb` has been executed from top to bottom successfully.
- DBLP-QuAD is converted: 7,000 training questions and 300 sampled test questions.
- The DBLP 2022 local store passes the publication probe. Gold answers are prepared
  for 270 test questions; 30 are dropped (9 empty results and 21 query syntax errors).
- DBLP statistics and Parquet are complete: 267,403,448 triples, 22 classes and 62
  properties; 74 schema entries remain after the minimum-frequency filter.
- DBpedia statistics and Parquet are complete: 50,141,876 triples, 439 classes and
  1,306 properties; 1,585 schema entries remain after the frequency filter.
- All checks in `kit/SETUP_REPORT.txt` pass with the active configuration.
- Gold answers are ready for 57 QALD questions and 69 LC-QuAD questions; dropped
  questions and reasons are saved alongside them.
- The 10-question model smoke test completed: accuracy 0.10, one partial answer,
  and mean model time 2.90 seconds per question. Raw outputs and scored results
  are in `kit/results/setup_smoke.jsonl` and `kit/results/setup_smoke.csv`.

`kit/SETUP_REPORT.txt` records the latest completed checks. The active graph
configuration uses `dbpedia2022` and `dblp2022`; source files and checksums are
documented in `kit/data/benchmarks/raw/SOURCES.md`.

Graph preparation runs inside the container, from `kit/`:

```bash
python -m sumqa.kgstore --store data/kg/dbpedia2022/store data/kg/dbpedia/raw/2022.12.01/*.ttl.bz2 data/kg/dbpedia2022/ontology.nt
python -m sumqa.kgstats --out data/kg/dbpedia2022/counts.json --parquet data/kg/dbpedia2022/parquet "data/kg/dbpedia/raw/2022.12.01/*.ttl.bz2"
python -m sumqa.build_schema --ontology data/kg/dbpedia2022/ontology.nt --counts data/kg/dbpedia2022/counts.json --out data/kg/dbpedia2022/schema_elements.jsonl
python -m sumqa.gold --bench data/benchmarks/qald9plus_test.jsonl --endpoint "$DBPEDIA_ENDPOINT" --kg dbpedia2022
python -m sumqa.gold --bench data/benchmarks/lcquad1_test.jsonl --endpoint "$DBPEDIA_ENDPOINT" --kg dbpedia2022
```

For the DBLP graph preparation commands, follow `kit/SETUP.md`. Fetch the pinned
ontology linked in `SOURCES.md` and convert it with rdflib to N-Triples before
running the DBpedia commands above. The large inputs remain outside Git.

For faster DBLP processing, split its gzip input into temporary N-Triples chunks
before running Spark (all triples are preserved):

```bash
mkdir -p /tmp/sumqa-dblp
gzip -dc data/kg/dblp2022/raw/dblp.nt.gz | split -l 1000000 -d -a 4 --additional-suffix=.nt - /tmp/sumqa-dblp/part-
python -m sumqa.kgstats --out data/kg/dblp2022/counts.json --parquet data/kg/dblp2022/parquet --driver-memory 8g "/tmp/sumqa-dblp/*.nt"
```

Run the 10-question setup smoke test from `kit/`:

```bash
python -m sumqa.run --bench data/benchmarks/qald9plus_test.gold.jsonl --kg dbpedia2022 --context retrieval --budget 1000 --model ollama:qwen2.5-coder:7b --team setup --limit 10 --out results/setup_smoke.jsonl
python -m sumqa.score results/setup_smoke.jsonl --results results/setup_smoke.csv
```

This short run checks the pipeline and model timing. Use the full test splits and
the team's assigned identifier for the graded baseline experiments.

## Files and results

`kit/data/toy/` is the correct location for the supplied toy data: the notebook,
runner and setup commands use that path. `B1` in the setup examples is a sample
team identifier; use the team's assigned identifier for actual experiments.

Large graphs, model weights, caches, generated toy answers, and raw DBLP-QuAD
downloads are ignored by Git. The converted DBLP-QuAD benchmarks, source fixes,
course environment files and setup report can be committed. The download scripts
handle the DBLP-QuAD loader compatibility issue and dblp's RDF/XML schema response.
The setup checker reports missing graph stores without aborting the report.
Local Oxigraph queries enforce the configured timeout in a separate process, so
an expensive query cannot hang a benchmark run. Timeout failures are not cached.
The regression checks are in `kit/tests/test_sparql.py`.

Regenerate the setup report from the repository root:

```powershell
docker exec -w /home/jovyan/work/kit hy562-spark-lab python scripts/check_setup.py
```
