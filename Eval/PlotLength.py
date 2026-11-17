# Libraries
import os
import pandas as pd
import matplotlib.pyplot as plt
from rerank_k import read_qrels, read_run, get_scores

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "HNSW")  # queries and qrels are in here
RUNS = os.path.join(BASE, "..", "Runs")
OUT = os.path.join(BASE, "length_plots")
os.makedirs(OUT, exist_ok=True)

# name in the plot -> start of the run file name (bm25_dev.txt, rrf_dl19.txt ...)
systems = {
    "BM25": "bm25",
    "Dense (HNSW)": "hnsw_m8_ef200",
    "Re-rank top 100": "rerank100",
    "Re-rank top 1000": "rerank1000",
    "RRF (BM25 + dense)": "rrf",
}

# query file and qrels file for each set
sets = {
    "dev": ("queries.dev.tsv", "qrels.dev.tsv"),
    "dl19": ("queries.eval.tsv", "qrels.eval.one.tsv"),
    "dl20": ("queries.eval.tsv", "qrels.eval.two.tsv"),
}

MIN_QUERIES = 3  # dont plot a length if it has less queries than this
metrics = ["MRR@10", "NDCG@10", "MAP"]

for name, (query_file, qrels_file) in sets.items():
    print("\n" + name)
    query_path = os.path.join(DATA, query_file)
    qrels_path = os.path.join(DATA, qrels_file)
    if not os.path.exists(query_path) or not os.path.exists(qrels_path):
        print("cant find the queries or qrels, skipping")
        continue

    # query length = number of words
    length = {}
    for line in open(query_path, encoding="utf-8"):
        parts = line.rstrip("\r\n").split("\t", 1)
        if len(parts) == 2:
            length[parts[0]] = len(parts[1].split())
    rels = read_qrels(qrels_path)
    level = 1 if name == "dev" else 2

    no_text = [q for q in rels if q not in length]
    if len(no_text) > 0:
        print(len(no_text), "queries in the qrels are not in", query_file)

    rows = []
    for system, prefix in systems.items():
        path = os.path.join(RUNS, f"{prefix}_{name}.txt")
        if not os.path.exists(path):
            print("no run file for", system)
            continue
        run = read_run(path)
        for qid in rels:
            if qid in run and qid in length:
                s = get_scores(run[qid], rels[qid], level)
                if s is not None:
                    rows.append([system, qid, length[qid]] + list(s))

    if len(rows) == 0:
        print("no runs found, skipping")
        continue

    df = pd.DataFrame(rows, columns=["system", "qid", "length"] + metrics)
    table = df.groupby(["system", "length"])[metrics].mean()
    table["n"] = df.groupby(["system", "length"]).size()
    table = table.reset_index()
    table.to_csv(os.path.join(OUT, f"length_table_{name}.csv"), index=False)
    print(table.round(3).to_string(index=False))

    table = table[table["n"] >= MIN_QUERIES]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, m in zip(axes, metrics):
        for system in systems:
            part = table[table["system"] == system]
            if len(part) > 0:
                ax.plot(part["length"], part[m], "o-", label=system)
        ax.set_xlabel("query length (words)")
        ax.set_ylabel("average " + m)
        ax.set_title(m)
        ax.legend(fontsize=8)
    fig.suptitle(f"{name}: score by query length ({df['qid'].nunique()} queries)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f"length_{name}.png"), dpi=150)
    plt.close()

print("\nsaved in", OUT)
