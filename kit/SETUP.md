# Project B: set-up (done by each team, first week)

Everything below is done by the team: no course server is involved. Plan one afternoon plus an evening of
loading. At the end, commit `SETUP_REPORT.txt` to your repository (deadline: Monday 9 November).

## What you need

| Item | Minimum | Notes |
|---|---|---|
| Laptop | 16 GB RAM, 50 GB free disk | at least one team member; the others can copy the prepared folders |
| Course environment | `04_Environment` (Docker: Spark 4.2, JupyterLab) | as in the assignments |
| Ollama | https://ollama.com (Windows, macOS, Linux) | runs the LLM locally; a GPU helps but is not required |
| Network | about 4 GB of downloads + 5 GB of models | DBpedia, dblp, Hugging Face, Ollama |

Keep `data/` and `cache/` outside cloud-synced folders (OneDrive, Dropbox, iCloud); both are in `.gitignore`.

## Steps

1. **Repository.** Create the team repository and copy this `kit` folder into it, inside the course folder that
   `04_Environment/docker-compose.yml` mounts, on a local disk.
2. **Environment.** `cd 04_Environment && docker compose up -d`, open a terminal in JupyterLab
   (http://localhost:8888, token `hy562`) and, in the kit folder: `pip install -r requirements.txt`.
   Re-run this command if the container is rebuilt.
3. **Toy pipeline** (2 minutes, no downloads):
   ```bash
   export TOY_ENDPOINT=file:data/toy/kg.nt
   python -m sumqa.gold --bench data/toy/toy_test.jsonl --endpoint $TOY_ENDPOINT
   python -m sumqa.run --bench data/toy/toy_test.gold.jsonl --kg toy --context retrieval --budget 150 --model mock:gold --team B1
   python -m sumqa.score runs/B1/toy_test__retrieval__150__mock-gold.jsonl
   ```
   Accuracy must be 1.0. Then run `ProjectB_starter.ipynb` once from top to bottom.
4. **Knowledge graphs** (downloads about 4 GB; loading DBpedia into the local store takes tens of minutes,
   dblp longer; run them overnight if needed):
   ```bash
   bash scripts/download_kgs.sh dbpedia
   python -m sumqa.kgstore --store data/kg/dbpedia2016/store data/kg/dbpedia2016/raw/*.ttl.bz2 data/kg/dbpedia2016/raw/dbpedia_2016-10.nt
   python -m sumqa.kgstats --out data/kg/dbpedia2016/counts.json --parquet data/kg/dbpedia2016/parquet "data/kg/dbpedia2016/raw/*.ttl.bz2"
   python -m sumqa.build_schema --ontology data/kg/dbpedia2016/raw/dbpedia_2016-10.nt --counts data/kg/dbpedia2016/counts.json --out data/kg/dbpedia2016/schema_elements.jsonl

   bash scripts/download_kgs.sh dblp
   python -m sumqa.kgstore --store data/kg/dblp2022/store data/kg/dblp2022/raw/dblp.nt.gz
   python -m sumqa.kgstats --out data/kg/dblp2022/counts.json --parquet data/kg/dblp2022/parquet --driver-memory 8g data/kg/dblp2022/raw/dblp.nt.gz
   python -m sumqa.build_schema --ontology data/kg/dblp2022/raw/schema.ttl --counts data/kg/dblp2022/counts.json --out data/kg/dblp2022/schema_elements.jsonl
   ```
   The store is a folder that the kit opens read-only; no server runs. Set, in every terminal
   (or in `~/.bashrc` of the container):
   ```bash
   export DBPEDIA_ENDPOINT=oxigraph:data/kg/dbpedia2016/store
   export DBLP_ENDPOINT=oxigraph:data/kg/dblp2022/store
   ```
   If `schema.ttl` of dblp did not download, get the dblp schema file from https://dblp.org/rdf/ and rerun the
   last command. Copy `data/kg/` to the other team members (it is large; a USB disk is fine).
5. **Benchmarks and gold answers:**
   ```bash
   bash scripts/download_benchmarks.sh          # adds DBLP-QuAD and converts all benchmarks
   for b in qald9plus_test lcquad1_test; do python -m sumqa.gold --bench data/benchmarks/$b.jsonl --endpoint $DBPEDIA_ENDPOINT; done
   python -m sumqa.gold --bench data/benchmarks/dblpquad_test.jsonl --endpoint $DBLP_ENDPOINT
   ```
   Every team builds the same store from the same files, so every team gets the same gold answers.
6. **Ollama and the models.** Install Ollama on your laptop and run `ollama pull qwen2.5-coder:7b` (and later
   `ollama pull llama3.1:8b`). The container reaches it at:
   - Windows and macOS (Docker Desktop): `export OLLAMA_HOST=http://host.docker.internal:11434`
   - Linux, or any system where the above does not work: run Ollama as a container on the course network,
   `docker run -d --name ollama --network hy562_default -v ollama:/root/.ollama ollama/ollama`,
     then `docker exec ollama ollama pull qwen2.5-coder:7b` and `export OLLAMA_HOST=http://ollama:11434`
     (with an NVIDIA GPU on Linux add `--gpus=all` to `docker run`).
7. **Smoke test with the real model** (10 questions):
   ```bash
   python -m sumqa.run --bench data/benchmarks/qald9plus_test.gold.jsonl --kg dbpedia2016 --context retrieval \
       --budget 1000 --model ollama:qwen2.5-coder:7b --team B1 --limit 10
   python -m sumqa.score runs/B1/qald9plus_test__retrieval__1000__ollama-qwen2.5-coder-7b.jsonl
   ```
   Note the seconds per question (`llm_seconds` in the run file): it tells you how long the full runs take
   on your machine. Plan the runs of section 5 of the project description with it.
8. **Report.**
   ```bash
   python scripts/check_setup.py
   git add SETUP_REPORT.txt && git commit -m "set-up report"
   ```

## Faster endpoint (optional)

If queries on the local store are slow for your summaries, you may run QLever yourselves
(`pip install qlever`, needs Docker; the configurations are in `qlever/`). Then set
`DBPEDIA_ENDPOINT=http://localhost:7016`. Same KG files, so the same answers.

## When something fails

- `pyoxigraph` or `tiktoken` missing after a container rebuild: `pip install -r requirements.txt` again.
- Out of disk while loading: the store needs several times the compressed size; free space or use an external disk.
- Ollama answers very slowly (more than 60 s per question): use the 3 B model `qwen2.5-coder:3b` for development,
  and run the final experiments on the fastest machine of the team.
- Ask the other Project B teams in the shared channel first: everybody runs the same steps.
