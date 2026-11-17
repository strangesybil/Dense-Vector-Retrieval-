import os
import glob
import time
import shutil
import tarfile
import h5py
import faiss
import psutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(BASE, "..", "Runs")
RESULTS = os.path.join(BASE, "results")

# M, efConstruction, efSearch
SETTINGS = [(4, 50, 50), (8, 100, 100), (8, 200, 200)]
RUN_FLAT = True
TOPK = 1000
LAT_QUERIES = 200  # how many queries we time one by one

passage_h5 = os.path.join(BASE, "msmarco_passages_embeddings_subset.h5")
passage_ids = os.path.join(BASE, "msmarco_passages_subset.tsv")
collection = os.path.join(BASE, "collection.tar.gz")
query_h5 = os.path.join(BASE, "msmarco_queries_dev_eval_embeddings.h5")
qrels_files = {
    "dev": os.path.join(BASE, "qrels.dev.tsv"),
    "dl19": os.path.join(BASE, "qrels.eval.one.tsv"),
    "dl20": os.path.join(BASE, "qrels.eval.two.tsv"),
}

# stop early if a file is missing
for f in [passage_h5, passage_ids, collection, query_h5] + list(qrels_files.values()):
    if not os.path.exists(f):
        print("missing:", f)
        raise SystemExit

# delete the old results, only our own files so the other runs in Runs/ stay
os.makedirs(RUNS, exist_ok=True)
for f in glob.glob(RUNS + "/hnsw_*.txt") + glob.glob(RUNS + "/flat_*.txt"):
    os.remove(f)
shutil.rmtree(RESULTS, ignore_errors=True)
shutil.rmtree(os.path.join(BASE, "runs"), ignore_errors=True)
os.makedirs(RESULTS)


def load_h5(path):
    with h5py.File(path, "r") as f:
        return np.array(f["id"]).astype(str), np.array(f["embedding"]).astype(np.float32)


def read_qrels(path):
    rels = {}
    for line in open(path):
        parts = line.split()
        rels.setdefault(parts[0], {})[parts[-2]] = int(parts[-1])
    return rels


def get_scores(run, rels):
    mrr, ndcg, ap = [], [], []
    for qid, docs in run.items():
        r = rels[qid]

        # mrr@10
        rr = 0
        for i, doc in enumerate(docs[:10]):
            if r.get(doc, 0) > 0:
                rr = 1 / (i + 1)
                break
        mrr.append(rr)

        # ndcg@10
        dcg = sum(r.get(doc, 0) / np.log2(i + 2) for i, doc in enumerate(docs[:10]))
        best = sorted(r.values(), reverse=True)[:10]
        idcg = sum(g / np.log2(i + 2) for i, g in enumerate(best))
        ndcg.append(dcg / idcg if idcg > 0 else 0)

        # average precision
        hits = 0
        total = 0
        for i, doc in enumerate(docs):
            if r.get(doc, 0) > 0:
                hits += 1
                total += hits / (i + 1)
        num_rel = sum(1 for g in r.values() if g > 0)
        ap.append(total / num_rel if num_rel > 0 else 0)

    return np.mean(mrr), np.mean(ndcg), np.mean(ap)


print("loading data")
pids, xb = load_h5(passage_h5)
pids = pids.tolist()  # row number in the index -> passage id
d = xb.shape[1]
print("passages:", xb.shape)

subset = pd.read_csv(passage_ids, sep="\t", header=None, dtype=str)[0].tolist()
assert len(subset) == len(pids), "tsv and h5 dont match"

# read the passage text from the collection
print("reading collection.tar.gz")
tar = tarfile.open(collection)
for member in tar:
    if member.name.endswith(".tsv"):
        f = tar.extractfile(member)
        break
wanted = set(subset)
texts = {}
for line in f:
    pid, text = line.decode("utf-8").rstrip("\r\n").split("\t", 1)
    if pid in wanted:
        texts[pid] = text
assert all(p in texts for p in pids), "some passages are not in the collection"

# only keep the queries that have qrels
all_qids, all_q = load_h5(query_h5)
row_of = {q: i for i, q in enumerate(all_qids.tolist())}
query_sets = {}
for name, path in qrels_files.items():
    rels = read_qrels(path)
    ids = [q for q in rels if q in row_of]
    query_sets[name] = (ids, all_q[[row_of[q] for q in ids]], rels)
    print(f"{name}: {len(ids)} queries")

# every index we want to try, flat goes last
configs = []
for M, efc, efs in SETTINGS:
    label = f"hnsw_m{M}_ef{efc}" if efc == efs else f"hnsw_m{M}_efc{efc}_efs{efs}"
    configs.append((label, M, efc, efs))
if RUN_FLAT:
    configs.append(("flat", None, None, None))

process = psutil.Process()
results = []

for n, (label, M, efc, efs) in enumerate(configs):
    print(f"\n[{n + 1}/{len(configs)}] {label}")

    ram_before = process.memory_info().rss / 1024 ** 2
    start = time.time()
    if M is None:
        index = faiss.IndexFlatIP(d)  # exact search
    else:
        index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = efc
    index.add(xb)
    build_time = time.time() - start
    ram = process.memory_info().rss / 1024 ** 2 - ram_before
    if M is not None:
        index.hnsw.efSearch = efs

    # latency = average time of one query at a time
    lat_vecs = query_sets["dev"][1][:LAT_QUERIES]
    start = time.time()
    for q in lat_vecs:
        index.search(q.reshape(1, -1), TOPK)
    latency = (time.time() - start) / len(lat_vecs) * 1000
    print(f"build {build_time:.1f}s | RAM +{ram:.0f} MB | latency {latency:.2f} ms/query")

    res = {"name": label, "M": M, "efC": efc, "efS": efs,
           "build_s": build_time, "ram_mb": ram, "latency_ms": latency}

    for name, (ids, vecs, rels) in query_sets.items():
        D, I = index.search(vecs, TOPK)
        run = {}
        # run file: qid Q0 pid rank score tag
        with open(os.path.join(RUNS, f"{label}_{name}.txt"), "w") as f:
            for qid, scores, rows in zip(ids, D.tolist(), I.tolist()):
                run[qid] = []
                for s, row in zip(scores, rows):
                    if row < 0:  # hnsw gives -1 when it cant find enough results
                        continue
                    run[qid].append(pids[row])
                    f.write(f"{qid} Q0 {pids[row]} {len(run[qid])} {s:.5f} {label}\n")

        mrr, ndcg, ap = get_scores(run, rels)
        res["mrr10_" + name] = mrr
        res["ndcg10_" + name] = ndcg
        res["map_" + name] = ap
        print(f"  {name:5s} MRR@10 {mrr:.3f} | NDCG@10 {ndcg:.3f} | MAP {ap:.3f}")

    results.append(res)
    # save as we go
    pd.DataFrame(results).to_csv(os.path.join(RESULTS, "results.csv"), index=False)
    del index  # free it so the RAM number of the next index is right

df = pd.DataFrame(results)
print("\nsummary")
print(df.drop(columns=["M", "efC", "efS"]).round(3).to_string(index=False))

# accuracy vs latency plot
hnsw = df[df["name"] != "flat"]
plt.figure(figsize=(7, 4.5))
for name in query_sets:
    line, = plt.plot(hnsw["latency_ms"], hnsw["mrr10_" + name], "o-", label=name + " HNSW")
    if RUN_FLAT:
        flat = df[df["name"] == "flat"].iloc[0]
        plt.scatter(flat["latency_ms"], flat["mrr10_" + name], marker="x", color=line.get_color(), label=name + " flat")
for _, r in hnsw.iterrows():
    plt.annotate(f"({int(r.M)},{int(r.efC)},{int(r.efS)})", (r.latency_ms, r.mrr10_dev))
plt.xlabel("latency per query (ms)")
plt.ylabel("MRR@10")
plt.title("accuracy vs latency")
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(RESULTS, "accuracy_vs_latency.png"), dpi=150)

print("\nrun files in", os.path.abspath(RUNS))
print("results in", RESULTS)
