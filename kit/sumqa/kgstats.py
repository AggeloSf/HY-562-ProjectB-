"""Class and property counts of a KG (PySpark). Used to order the schema baselines.

    python -m sumqa.kgstats --out data/kg/dbpedia2016/counts.json "data/kg/dbpedia2016/raw/*.ttl.bz2"
    python -m sumqa.kgstats --out data/kg/dblp2022/counts.json data/kg/dblp2022/raw/dblp.nt.gz

Writes {"classes": {iri: instances}, "properties": {iri: triples}, "triples": n}.
Also converts the KG to Parquet (--parquet DIR) so that summary code reads it fast:
columns s, p, o, okind ("iri" | "bnode" | "literal"), dt, lang.
"""
import argparse
import json

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
NT_REGEX = r'^\s*(<[^>]*>|_:\S+)\s+<([^>]*)>\s+(.*?)\s*\.\s*$'
OBJ_LIT = r'^"((?:[^"\\]|\\.)*)"(?:@([A-Za-z0-9-]+)|\^\^<([^>]*)>)?$'


def load_triples(spark, paths):
    lines = spark.read.text(paths).filter(~F.col("value").rlike(r"^\s*(#.*)?$"))
    x = lines.select(F.regexp_extract("value", NT_REGEX, 1).alias("s_raw"),
                     F.regexp_extract("value", NT_REGEX, 2).alias("p"),
                     F.regexp_extract("value", NT_REGEX, 3).alias("o_raw")).filter(F.col("p") != "")
    iri = F.col("o_raw").startswith("<")
    bn = F.col("o_raw").startswith("_:")
    lang = F.regexp_extract("o_raw", OBJ_LIT, 2)
    dt = F.regexp_extract("o_raw", OBJ_LIT, 3)
    return x.select(
        F.when(F.col("s_raw").startswith("<"), F.expr("substring(s_raw, 2, length(s_raw) - 2)"))
         .otherwise(F.col("s_raw")).alias("s"),
        "p",
        F.when(iri, F.expr("substring(o_raw, 2, length(o_raw) - 2)")).when(bn, F.col("o_raw"))
         .otherwise(F.regexp_extract("o_raw", OBJ_LIT, 1)).alias("o"),
        F.when(iri, "iri").when(bn, "bnode").otherwise("literal").alias("okind"),
        F.when(iri | bn, F.lit(None)).when(lang != "", "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")
         .when(dt != "", dt).otherwise("http://www.w3.org/2001/XMLSchema#string").alias("dt"),
        F.when(lang != "", lang).alias("lang"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--parquet", default=None)
    ap.add_argument("--driver-memory", default="4g")
    ap.add_argument("paths", nargs="+")
    a = ap.parse_args()
    spark = (SparkSession.builder.appName("kgstats").config("spark.driver.memory", a.driver_memory)
             .config("spark.sql.shuffle.partitions", "16").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    t = load_triples(spark, a.paths)
    if a.parquet:
        t.write.mode("overwrite").parquet(a.parquet)
        t = spark.read.parquet(a.parquet)
    classes = {r["o"]: r["n"] for r in t.filter(F.col("p") == RDF_TYPE).groupBy("o")
               .agg(F.countDistinct("s").alias("n")).collect()}
    props = {r["p"]: r["n"] for r in t.groupBy("p").count().withColumnRenamed("count", "n").collect()}
    with open(a.out, "w") as f:
        json.dump({"classes": classes, "properties": props, "triples": sum(props.values())}, f)
    print(f"{len(classes)} classes, {len(props)} properties, {sum(props.values())} triples -> {a.out}")
    spark.stop()


if __name__ == "__main__":
    main()
