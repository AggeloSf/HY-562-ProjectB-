#!/usr/bin/env bash
# Knowledge graphs for Project B. Every team runs this on (at least) one machine; see SETUP.md.
#   bash scripts/download_kgs.sh dbpedia     # about 1.1 GB compressed
#   bash scripts/download_kgs.sh dblp        # about 2.8 GB compressed
set -euo pipefail
case "${1:-}" in
dbpedia)
  # DBpedia 2016-10, the release used by QALD-9 (CC BY-SA 3.0 / GFDL). Files from
  # https://downloads.dbpedia.org/2016-10/core-i18n/en/ and the ontology from /2016-10/
  D=data/kg/dbpedia2016/raw; mkdir -p $D
  B=https://downloads.dbpedia.org/2016-10/core-i18n/en
  for f in instance_types_en.ttl.bz2 instance_types_transitive_en.ttl.bz2 mappingbased_objects_en.ttl.bz2 \
           mappingbased_literals_en.ttl.bz2 labels_en.ttl.bz2 infobox_properties_en.ttl.bz2; do
    [ -s $D/$f ] || curl -fL --retry 3 -o $D/$f $B/$f
  done
  [ -s $D/dbpedia_2016-10.nt ] || curl -fL -o $D/dbpedia_2016-10.nt https://downloads.dbpedia.org/2016-10/dbpedia_2016-10.nt
  echo "next: python -m sumqa.kgstore --store data/kg/dbpedia2016/store $D/*.ttl.bz2 $D/dbpedia_2016-10.nt"
  echo "      python -m sumqa.kgstats --out data/kg/dbpedia2016/counts.json --parquet data/kg/dbpedia2016/parquet \"$D/*.ttl.bz2\""
  echo "      python -m sumqa.build_schema --ontology $D/dbpedia_2016-10.nt --counts data/kg/dbpedia2016/counts.json --out data/kg/dbpedia2016/schema_elements.jsonl"
  ;;
dblp)
  # dblp RDF dump of 1 Aug 2022, the KG version of DBLP-QuAD (CC BY 4.0), Zenodo 10.5281/zenodo.7638511
  D=data/kg/dblp2022/raw; mkdir -p $D
  [ -s $D/dblp.nt.gz ] || curl -fL --retry 3 -o $D/dblp.nt.gz "https://zenodo.org/records/7638511/files/dblp.nt.gz?download=1"
  # dblp schema (ontology); check the address on https://dblp.org/rdf/ if this fails
  [ -s $D/schema.ttl ] || curl -fL -H "Accept: text/turtle" -o $D/schema.ttl https://dblp.org/rdf/schema || echo "schema download failed: get it from https://dblp.org/rdf/"
  echo "next: python -m sumqa.kgstore --store data/kg/dblp2022/store $D/dblp.nt.gz"
  echo "      python -m sumqa.kgstats --out data/kg/dblp2022/counts.json --parquet data/kg/dblp2022/parquet --driver-memory 8g $D/dblp.nt.gz"
  echo "      python -m sumqa.build_schema --ontology $D/schema.ttl --counts data/kg/dblp2022/counts.json --out data/kg/dblp2022/schema_elements.jsonl"
  ;;
*) echo "usage: $0 dbpedia|dblp"; exit 1;;
esac
