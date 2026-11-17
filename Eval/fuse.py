# Libraries 
import os
from rerank_k import read_run

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(BASE, "..", "Runs")

K = 60
KEEP = 1000  # how many docs we keep per query

sets = ["dev", "dl19", "dl20"]

# dense run to fuse with bm25, we use the first one that exists
# (the rerank one is the backup if the hnsw run isnt ready)
dense_options = ["hnsw_m8_ef200", "rerank1000"]

for name in sets:
    print(name)

    bm25_file = os.path.join(RUNS, f"bm25_{name}.txt")
    if not os.path.exists(bm25_file):
        print("no bm25 file, skipping")
        continue

    dense_file = None
    for option in dense_options:
        f = os.path.join(RUNS, f"{option}_{name}.txt")
        if os.path.exists(f):
            dense_file = f
            print("fusing bm25 with", option)
            break
    if dense_file is None:
        print("no dense run found, skipping")
        continue

    bm25 = read_run(bm25_file, KEEP)
    dense = read_run(dense_file, KEEP)

    out = open(os.path.join(RUNS, f"rrf_{name}.txt"), "w")
    for qid in bm25:
        if qid not in dense:
            continue

        # rrf: every doc gets 1 / (K + rank) from each list and we add them up
        scores = {}
        for docs in [bm25[qid], dense[qid]]:
            for i, doc in enumerate(docs):
                rank = i + 1
                scores[doc] = scores.get(doc, 0) + 1 / (K + rank)

        ranked = sorted(scores, key=scores.get, reverse=True)[:KEEP]
        for i, doc in enumerate(ranked):
            out.write(f"{qid} Q0 {doc} {i + 1} {scores[doc]:.8f} rrf\n")
    out.close()
    print("wrote rrf_" + name + ".txt")
