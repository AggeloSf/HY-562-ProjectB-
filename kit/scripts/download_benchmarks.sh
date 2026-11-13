#!/usr/bin/env bash
# QALD-9-plus and LC-QuAD 1.0 are already in data/benchmarks/raw. This script adds DBLP-QuAD
# from Hugging Face (needs: pip install datasets) and then converts all benchmarks.
#   bash scripts/download_benchmarks.sh
set -euo pipefail
RAW=data/benchmarks/raw
mkdir -p $RAW/dblp_quad
python - <<'PY'
import json
from datasets import load_dataset
ds = load_dataset("awalesushil/DBLP-QuAD")
for split, name in [("train", "train"), ("validation", "valid"), ("test", "test")]:
    if split in ds:
        rows = [dict(r) for r in ds[split]]
        json.dump(rows, open(f"data/benchmarks/raw/dblp_quad/{name}.json", "w"))
        print(split, len(rows), "fields:", sorted(rows[0].keys()))
PY
python -m sumqa.prepare_benchmarks --raw $RAW --out data/benchmarks
