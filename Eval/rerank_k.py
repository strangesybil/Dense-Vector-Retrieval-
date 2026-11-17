# libraries
import os
import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "HNSW")  # embeddings and qrels are in here
RUNS = os.path.join(BASE, "..", "Runs")
OUT = os.path.join(BASE, "rerank_plots")


def load_h5(path):  # ids as strings, embeddings as float32
    with h5py.File(path, "r") as f:
        return np.array(f["id"]).astype(str), np.array(f["embedding"]).astype(np.float32)


def read_qrels(path):  # {query id: {passage id: relevance}}
    rels = {}
    for line in open(path):
        parts = line.split()
        rels.setdefault(parts[0], {})[parts[-2]] = int(parts[-1])
    return rels


def read_run(path, depth=1000):  # {query id: [passage ids, best first]}
    run = {}
    for line in open(path):
        parts = line.split()
        run.setdefault(parts[0], []).append((float(parts[4]), parts[2]))
    # same order as trec_eval: highest score first, the bigger docno wins a tie
    return {q: [doc for _, doc in sorted(pairs, reverse=True)[:depth]] for q, pairs in run.items()}


def get_scores(docs, rels, level):
    # level = lowest grade that counts as relevant (1 for dev, 2 for dl19 and dl20)
    num_rel = sum(g >= level for g in rels.values())
    if num_rel == 0:
        return None  # trec_eval skips queries with nothing relevant

    # mrr@10
    mrr = 0
    for i, doc in enumerate(docs[:10]):
        if rels.get(doc, 0) >= level:
            mrr = 1 / (i + 1)
            break

    # ndcg@10
    dcg = sum(rels.get(doc, 0) / np.log2(i + 2) for i, doc in enumerate(docs[:10]))
    best = sorted(rels.values(), reverse=True)[:10]
    idcg = sum(g / np.log2(i + 2) for i, g in enumerate(best))

    # average precision
    hits = 0
    total = 0
    for i, doc in enumerate(docs):
        if rels.get(doc, 0) >= level:
            hits += 1
            total += hits / (i + 1)

    return mrr, dcg / idcg, total / num_rel


def average(run, rels, level):  # mean of the three scores over all queries
    scores = [get_scores(docs, rels[qid], level) for qid, docs in run.items()]
    return np.mean([s for s in scores if s is not None], axis=0)


# fuse.py and PlotLength.py import the functions above, this part only runs on its own
if __name__ == "__main__":
    KS = list(range(10, 101, 10))
    sets = {"dev": "qrels.dev.tsv", "dl19": "qrels.eval.one.tsv", "dl20": "qrels.eval.two.tsv"}
    metrics = ["MRR@10", "NDCG@10", "MAP"]
    os.makedirs(OUT, exist_ok=True)

    print("loading embeddings")
    pids, passage_vecs = load_h5(os.path.join(DATA, "msmarco_passages_embeddings_subset.h5"))
    qids, query_vecs = load_h5(os.path.join(DATA, "msmarco_queries_dev_eval_embeddings.h5"))
    passage_row = {p: i for i, p in enumerate(pids.tolist())}  # id -> row in the embeddings
    query_row = {q: i for i, q in enumerate(qids.tolist())}

    results = []
    for name, qrels_file in sets.items():
        print("\n" + name)
        qrels_path = os.path.join(DATA, qrels_file)
        bm25_path = os.path.join(RUNS, f"bm25_{name}.txt")
        if not (os.path.exists(qrels_path) and os.path.exists(bm25_path)):
            print("cant find the qrels or the bm25 run, skipping")
            continue

        rels = read_qrels(qrels_path)
        level = 1 if name == "dev" else 2
        bm25 = {q: d for q, d in read_run(bm25_path).items() if q in rels and q in query_row}
        print(f"{len(bm25)} queries")

        # dense score (dot product) for the top 100 bm25 docs of every query
        dense = {}
        for qid, docs in bm25.items():
            rows = np.array([passage_row.get(doc, -1) for doc in docs[:KS[-1]]])
            dense[qid] = passage_vecs[rows] @ query_vecs[query_row[qid]]
            dense[qid][rows < 0] = -1e9  # no embedding for this passage, it goes to the bottom

        base = average(bm25, rels, level)
        print("bm25 alone:  MRR@10 %.3f | NDCG@10 %.3f | MAP %.3f" % tuple(base))

        for k in KS:
            # re-rank only the first k bm25 results, the rest stay in bm25 order
            reranked = {}
            for qid, docs in bm25.items():
                order = np.argsort(-dense[qid][:k], kind="stable")
                reranked[qid] = [docs[i] for i in order] + docs[k:]
            new = average(reranked, rels, level)
            change = new - base
            results.append([name, k] + list(new) + list(change))
            print(f"k={k:3d}  change in MRR@10 {change[0]:+.3f} | NDCG@10 {change[1]:+.3f} | MAP {change[2]:+.3f}")

    if not results:
        raise SystemExit("nothing to plot")

    df = pd.DataFrame(results, columns=["set", "k"] + metrics + ["change " + m for m in metrics])
    df.to_csv(os.path.join(OUT, "rerank_results.csv"), index=False)

    # one panel per metric, one line per query set
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, m in zip(axes, metrics):
        for name, part in df.groupby("set"):
            ax.plot(part["k"], part["change " + m], "o-", label=name)
        ax.axhline(0, color="gray", linestyle="--")  # zero = same as bm25
        ax.set_xlabel("k (bm25 results re-ranked)")
        ax.set_ylabel("change in " + m)
        ax.set_title(m)
        ax.legend()
    fig.suptitle("change when the bm25 top k is re-ranked with dense scores")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "rerank_change_vs_k.png"), dpi=150)
    print("\nsaved in", OUT)