#!/usr/bin/env bash
# QALD-9-plus and LC-QuAD 1.0 are already in data/benchmarks/raw. This script adds DBLP-QuAD
# from the archive used by Hugging Face and then converts all benchmarks.
#   bash scripts/download_benchmarks.sh
set -euo pipefail
RAW=data/benchmarks/raw
mkdir -p $RAW/dblp_quad
python - <<'PY'
import json
import tempfile
import urllib.request
import zipfile

# The Hugging Face dataset loader points to this archive. Recent datasets
# versions no longer support the repository's custom loading script.
url = "https://zenodo.org/record/7643971/files/DBLP-QuAD.zip"
with tempfile.TemporaryFile() as archive:
    with urllib.request.urlopen(url) as response:
        while chunk := response.read(1024 * 1024):
            archive.write(chunk)
    archive.seek(0)
    with zipfile.ZipFile(archive) as dataset:
        for name in ("train", "valid", "test"):
            with dataset.open(f"DBLP-QuAD/{name}/questions.json") as source:
                rows = json.load(source)["questions"]
            with open(f"data/benchmarks/raw/dblp_quad/{name}.json", "w", encoding="utf-8") as target:
                json.dump(rows, target)
            print(name, len(rows), "fields:", sorted(rows[0].keys()))
PY
python -m sumqa.prepare_benchmarks --raw $RAW --out data/benchmarks
