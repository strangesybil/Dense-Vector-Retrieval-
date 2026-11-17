# Libraries
import os
import time
import h5py
import faiss
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")

# M, efConstruction, efSearch
SETTINGS = [(4, 50, 50), (8, 100, 100), (8, 200, 200)]
TOPK = 1000

passage_h5 = os.path.join(BASE, "msmarco_passages_embeddings_subset.h5")
query_h5 = os.path.join(BASE, "msmarco_queries_dev_eval_embeddings.h5")
qrels_files = {
    "dl19": os.path.join(BASE, "qrels.eval.one.tsv"),
    "dl20": os.path.join(BASE, "qrels.eval.two.tsv"),
    "dev": os.path.join(BASE, "qrels.dev.tsv"),
}

# Stop early if a file is missing esn a saftey check
for f in [passage_h5, query_h5] + list(qrels_files.values()):
    if not os.path.exists(f):
        print("missing:", f)
        raise SystemExit


def load_h5(path):
    with h5py.File(path, "r") as f:
        return np.array(f["id"]).astype(str), np.array(f["embedding"]).astype(np.float32)


print("loading data")
_, xb = load_h5(passage_h5)
d = xb.shape[1]
all_qids, all_q = load_h5(query_h5)
row_of = {q: i for i, q in enumerate(all_qids.tolist())}

# only the judged queries, same as hnsw.py
query_sets = {}
for name, path in qrels_files.items():
    ids = {line.split()[0] for line in open(path)}
    rows = [row_of[q] for q in ids if q in row_of]
    query_sets[name] = all_q[rows]
    print(f"{name}: {len(rows)} queries")

os.makedirs(RESULTS, exist_ok=True)
rows_out = [] # list that collect one row per index and query set

for M, efc, efs in SETTINGS:
    label = f"hnsw_m{M}_ef{efc}" if efc == efs else f"hnsw_m{M}_efc{efc}_efs{efs}"
    print(f"\n{label}")
    index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = efc
    index.add(xb)
    index.hnsw.efSearch = efs

    # a few warm up searches so the first query is not slow
    for q in query_sets["dev"][:20]:
        index.search(q.reshape(1, -1), TOPK)

    for name, vecs in query_sets.items(): # times each query set seperately 
        times = []
        for q in vecs:
            start = time.perf_counter()
            index.search(q.reshape(1, -1), TOPK)
            times.append((time.perf_counter() - start) * 1000)
        avg = np.mean(times)
        p95 = np.percentile(times, 95)
        print(f"  {name:5s} avg {avg:.2f} ms | p95 {p95:.2f} ms")
        rows_out.append({"name": label, "set": name, "avg_ms": avg, "p95_ms": p95})
    del index

pd.DataFrame(rows_out).round(2).to_csv(os.path.join(RESULTS, "latency.csv"), index=False)
print("\nsaved results/latency.csv")
