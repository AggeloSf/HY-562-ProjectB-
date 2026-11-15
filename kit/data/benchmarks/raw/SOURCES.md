# Benchmark files in this folder

| File | Benchmark | Source | License |
|---|---|---|---|
| `qald_9_plus_train_dbpedia.json`, `qald_9_plus_test_dbpedia.json` | QALD-9-plus, DBpedia part (408 train, 150 test) | https://github.com/KGQA/QALD_9_plus | CC BY 4.0 |
| `lcquad1_train.json`, `lcquad1_test.json` | LC-QuAD 1.0 (4,000 train, 1,000 test), DBpedia 2016-04 | https://github.com/AskNowQA/LC-QuAD (branch `data`) | GPL-3.0 |
| `dblp_quad/` (downloaded by `scripts/download_benchmarks.sh`) | DBLP-QuAD (7,000 train, 1,000 valid, 2,000 test) | https://huggingface.co/datasets/awalesushil/DBLP-QuAD | CC BY 4.0 |

Cite in your report:
- A. Perevalov, D. Diefenbach, R. Usbeck, A. Both. QALD-9-plus: A Multilingual Dataset for Question Answering over DBpedia and Wikidata Translated by Native Speakers. ICSC 2022.
- P. Trivedi, G. Maheshwari, M. Dubey, J. Lehmann. LC-QuAD: A Corpus for Complex Question Answering over Knowledge Graphs. ISWC 2017.
- D. Banerjee, S. Awale, R. Usbeck, C. Biemann. DBLP-QuAD: A Question Answering Dataset over the DBLP Scholarly Knowledge Graph. arXiv:2303.13351, 2023.

## Local graph inputs for this repository

The active DBpedia input is the three compressed raw files in
`data/kg/dbpedia/raw/2022.12.01/`. The sampled Parquet snapshots and streaming
epochs are not inputs to SumQA. Derived files are written to `data/kg/dbpedia2022/`
and runs use `--kg dbpedia2022`.

| Raw file | SHA-256 |
|---|---|
| `instance-types_lang=en_specific.ttl.bz2` | `59dc900bea2ec126b8c2a4097be4ccab5f737bf4616a3f1a9d300942e32c2c3e` |
| `mappingbased-literals_lang=en.ttl.bz2` | `094b566bc9983842b1e97cecb2119c0e0f640e0a13882cf3f294b91b02ab770a` |
| `mappingbased-objects_lang=en.ttl.bz2` | `76747563b7bb6587d8707ae65489186b54d17acec060da7566397992c171371a` |

Schema vocabulary comes from the official DBpedia ontology tracker, pinned to
commit `99e1e11169523ee215dc33b8719a5b74c406a1ed` (28 December 2018):
https://raw.githubusercontent.com/dbpedia/ontology-tracker/99e1e11169523ee215dc33b8719a5b74c406a1ed/ontology/ontology.owl.
It is converted to N-Triples locally for the query store and schema builder.

DBLP uses the 1 August 2022 dump from https://zenodo.org/records/7638511,
`dblp.nt.gz`, MD5 `8194e6e98fef690ba3d24afe488fa2d8`. Gold and dropped-question
files are regenerated against the local stores; keep the dropped-question lists
with the reported accuracy.
