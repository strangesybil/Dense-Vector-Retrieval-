import subprocess, os
import matplotlib.pyplot as plt

TREC_EVAL = "../trec_eval/trec_eval"

def trecfairy(qrels, run, flags): #running the trec eval with the flags
    res = subprocess.run([TREC_EVAL] + flags + [qrels, run], capture_output=True, text=True)
    if not res.stdout.strip():
        print("eval failed on this run:", run, " because ", flags)
        print(res.stderr)
        exit(1)
    return float(res.stdout.split()[-1]) #change to float

def truncate(source, k, destination):
    count = {} #dictionary from qid to how many lines from that query
    with open(source) as ref, open(destination, "w") as g:
        for line in ref: #read 
            qid = line.split()[0]
            count[qid] = count.get(qid, 0) + 1
            if count[qid] <= k:
                g.write(line)
    return destination

QRELS = {
    "dl19": "Data/qrels.eval.one.tsv",
    "dl20": "Data/qrels.eval.two.tsv",
    "dev":  "Data/qrels.dev.trec.tsv",
}

def graded(k):
    return {
        "MRR@k":    ["-l", "2", "-M", str(k), "-m", "recip_rank"],
        "Recall@k": ["-l", "2", "-m", f"recall.{k}"],
        "NDCG@k":   ["-m", f"ndcg_cut.{k}"],
        "MAP@k":    ["-l", "2", "-m", "map"],
}

def binary(k):
    return {
        "MRR@k":    ["-M", str(k), "-m", "recip_rank"],
        "Recall@k": ["-m", f"recall.{k}"],
        "MAP@k":    ["-m", "map"],
    }
KS = list(range(10, 101, 10))
os.makedirs("Eval/ploteval", exist_ok=True)
os.makedirs("Runs/topk", exist_ok=True)

for name, qrels in QRELS.items():
    measures = binary if name == "dev" else graded
    # make top-k versions of both runs once per k
    bm25_k, rerank_k = {}, {}
    for k in KS:
        bm25_k[k]   = truncate(f"Runs/bm25_{name}.txt", k, f"Runs/topk/bm25{k}_{name}.txt")
        rerank_k[k] = truncate(f"Runs/ksweep/rerank{k}_{name}.txt", k, f"Runs/topk/rerank{k}_{name}.txt")

    plt.figure(figsize=(8.5, 4.5))
    for metric in measures(10):
        rr = [trecfairy(qrels, rerank_k[k],measures(k)[metric]) for k in KS]
        bm = [trecfairy(qrels, bm25_k[k], measures(k)[metric]) for k in KS]
        line, = plt.plot(KS, rr, marker="o", label=f"re-ranked {metric}")
        plt.plot(KS, bm, linestyle="--", marker="o", color=line.get_color(), label=f"{metric} - BM25")
        print(name, metric, "BM25 by k:", [round(v, 3) for v in bm])
        print(name, metric, "rerank by k:", [round(v, 3) for v in rr])

    plt.title(f"{name}: Initial BM25 top k vs re-ranked top k (dashed = BM25 initial)")
    plt.xlabel("k (Number of BM25 results kept / re-ranked)")
    plt.ylabel("score")
    plt.xticks(KS)
    plt.grid(alpha=0.3)
    plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.savefig(f"Eval/ploteval/ksweep_{name}.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("saved", f"Eval/ploteval/ksweep_{name}.png")