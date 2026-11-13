"""Toy KG, ontology and 12 questions, to test a pipeline in seconds without a server.

    python scripts/make_toy.py            -> data/toy/{kg.nt, ontology.nt, counts.json,
                                             schema_elements.jsonl, toy_test.jsonl}
Then:
    export TOY_ENDPOINT=file:data/toy/kg.nt
    python -m sumqa.gold --bench data/toy/toy_test.jsonl --endpoint $TOY_ENDPOINT
    python -m sumqa.run --bench data/toy/toy_test.gold.jsonl --kg toy --context ontology --model mock:gold
"""
import json
import os
import random
import subprocess
import sys

EX, ON = "http://example.org/resource/", "http://example.org/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"

ONT = {  # class: superclass
    "Place": None, "City": "Place", "Country": "Place", "Agent": None, "Person": "Agent", "Scientist": "Person",
    "Organisation": "Agent", "University": "Organisation", "Company": "Organisation", "Work": None, "Film": "Work"}
PROPS = {  # property: (domain, range)
    "birthPlace": ("Person", "Place"), "employer": ("Person", "Organisation"), "almaMater": ("Person", "University"),
    "country": ("Place", "Country"), "location": ("Organisation", "City"), "director": ("Film", "Person"),
    "starring": ("Film", "Person"), "name": (None, "xsd:string"), "birthDate": ("Person", "xsd:date"),
    "population": ("Place", "xsd:integer"), "runtime": ("Film", "xsd:double"), "title": ("Work", "xsd:string")}

QUESTIONS = [
    ("In which city was Ada Lovelace born?", "SELECT ?c WHERE { exr:Ada_Lovelace ex:birthPlace ?c }"),
    ("In which country is Athens?", "SELECT ?c WHERE { exr:Athens ex:country ?c }"),
    ("Who directed The Long Night?", "SELECT ?p WHERE { exr:The_Long_Night ex:director ?p }"),
    ("Which films star Alan Turing?", "SELECT ?f WHERE { ?f ex:starring exr:Alan_Turing }"),
    ("How many people were born in Heraklion?",
     "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p ex:birthPlace exr:Heraklion }"),
    ("Is Heraklion in Greece?", "ASK { exr:Heraklion ex:country exr:Greece }"),
    ("Which scientists work for FORTH?",
     "SELECT ?p WHERE { ?p a ex:Scientist ; ex:employer exr:FORTH }"),
    ("Where is the University of Crete located?", "SELECT ?c WHERE { exr:University_of_Crete ex:location ?c }"),
    ("What is the population of Athens?", "SELECT ?n WHERE { exr:Athens ex:population ?n }"),
    ("Which films did Alan Turing direct?", "SELECT ?f WHERE { ?f ex:director exr:Alan_Turing }"),
    ("Who studied at the University of Crete and was born in Athens?",
     "SELECT ?p WHERE { ?p ex:almaMater exr:University_of_Crete ; ex:birthPlace exr:Athens }"),
    ("When was Ada Lovelace born?", "SELECT ?d WHERE { exr:Ada_Lovelace ex:birthDate ?d }"),
]


def main(out="data/toy"):
    os.makedirs(out, exist_ok=True)
    rng = random.Random(7)
    T = set()

    def t(s, p, o):
        T.add(f"<{s}> <{p}> {o} .")

    def iri(x):
        return f"<{EX}{x}>"

    named_cities = {"Heraklion": "Greece", "Athens": "Greece", "Lyon": "France", "London": "United_Kingdom"}
    for c in set(named_cities.values()):
        t(EX + c, RDF + "type", f"<{ON}Country>")
        t(EX + c, ON + "name", f'"{c.replace("_", " ")}"')
    cities = list(named_cities) + [f"City_{i}" for i in range(20)]
    for c in cities:
        t(EX + c, RDF + "type", f"<{ON}City>")
        t(EX + c, ON + "name", f'"{c}"')
        t(EX + c, ON + "country", iri(named_cities.get(c, rng.choice(list(set(named_cities.values()))))))
        t(EX + c, ON + "population", f'"{rng.randint(10_000, 4_000_000)}"^^<{XSD}integer>')
    orgs = {"FORTH": "Company", "University_of_Crete": "University", "Org_A": "Company", "Org_B": "University"}
    for o, k in orgs.items():
        t(EX + o, RDF + "type", f"<{ON}{k}>")
        t(EX + o, ON + "location", iri("Heraklion" if o != "Org_A" else "Lyon"))
    people = ["Ada_Lovelace", "Alan_Turing", "Grace_Hopper"] + [f"Person_{i}" for i in range(80)]
    for p in people:
        t(EX + p, RDF + "type", f"<{ON}{'Scientist' if rng.random() < 0.4 else 'Person'}>")
        t(EX + p, ON + "name", f'"{p.replace("_", " ")}"@en')
        t(EX + p, ON + "birthPlace", iri(rng.choice(cities[:6])))
        t(EX + p, ON + "birthDate", f'"19{rng.randint(10, 99)}-01-01"^^<{XSD}date>')
        t(EX + p, ON + "employer", iri(rng.choice(list(orgs))))
        if rng.random() < 0.5:
            t(EX + p, ON + "almaMater", iri(rng.choice(["University_of_Crete", "Org_B"])))
    t(EX + "Ada_Lovelace", ON + "birthPlace", iri("London"))
    t(EX + "Person_1", ON + "almaMater", iri("University_of_Crete"))
    t(EX + "Person_1", ON + "birthPlace", iri("Athens"))
    t(EX + "Person_2", RDF + "type", f"<{ON}Scientist>")
    t(EX + "Person_2", ON + "employer", iri("FORTH"))
    films = ["The_Long_Night"] + [f"Film_{i}" for i in range(30)]
    for f in films:
        t(EX + f, RDF + "type", f"<{ON}Film>")
        t(EX + f, ON + "title", f'"{f.replace("_", " ")}"@en')
        t(EX + f, ON + "director", iri(rng.choice(people)))
        for _ in range(rng.randint(1, 3)):
            t(EX + f, ON + "starring", iri(rng.choice(people)))
        t(EX + f, ON + "runtime", f'"{rng.randint(80, 180)}.0"^^<{XSD}double>')
    t(EX + "Film_3", ON + "starring", iri("Alan_Turing"))
    t(EX + "Film_4", ON + "director", iri("Alan_Turing"))
    with open(f"{out}/kg.nt", "w") as fh:
        fh.write("\n".join(sorted(T)) + "\n")

    O = []
    for c, sup in ONT.items():
        O.append(f"<{ON}{c}> <{RDF}type> <{OWL}Class> .")
        O.append(f'<{ON}{c}> <{RDFS}label> "{c.lower()}"@en .')
        if sup:
            O.append(f"<{ON}{c}> <{RDFS}subClassOf> <{ON}{sup}> .")
    for p, (d, r) in PROPS.items():
        O.append(f"<{ON}{p}> <{RDF}type> <{OWL}ObjectProperty> .")
        if d:
            O.append(f"<{ON}{p}> <{RDFS}domain> <{ON}{d}> .")
        O.append(f"<{ON}{p}> <{RDFS}range> <{XSD + r[4:] if r.startswith('xsd:') else ON + r}> .")
    with open(f"{out}/ontology.nt", "w") as fh:
        fh.write("\n".join(O) + "\n")

    # counts without Spark (the real KGs use sumqa.kgstats)
    from collections import Counter
    cls, prop = Counter(), Counter()
    for line in T:
        s, p, o = line[:-2].split(" ", 2)
        prop[p[1:-1]] += 1
        if p[1:-1] == RDF + "type":
            cls[o[1:-1]] += 1
    json.dump({"classes": cls, "properties": prop, "triples": len(T)}, open(f"{out}/counts.json", "w"))

    with open(f"{out}/toy_test.jsonl", "w") as fh:
        for i, (q, s) in enumerate(QUESTIONS):
            ents = sorted({EX + w[4:] for w in s.replace("}", " ").split() if w.startswith("exr:")})
            fh.write(json.dumps({"id": f"toy-{i}", "benchmark": "toy", "kg": "toy", "question": q,
                                 "sparql": f"PREFIX ex: <{ON}> PREFIX exr: <{EX}> {s}", "entities": ents}) + "\n")
    subprocess.run([sys.executable, "-m", "sumqa.build_schema", "--ontology", f"{out}/ontology.nt",
                    "--counts", f"{out}/counts.json", "--out", f"{out}/schema_elements.jsonl", "--min-count", "1"],
                   check=True)
    print(f"toy KG: {len(T)} triples, {len(QUESTIONS)} questions -> {out}")


if __name__ == "__main__":
    main()
