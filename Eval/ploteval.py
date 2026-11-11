import subprocess,os,matplotlib.pyplot as plt

TREC_EVAL = "../trec_eval/trec_eval"

def trecfairy(qrels,run,flags):
    res=subprocess.run([TREC_EVAL]+flags+[qrels,run],capture_output=True,text=True)
    if not res.stdout.strip():
        print("eval failed on this run:",run," because ",flags)
        print(res.stderr)
        exit(1)
    return float(res.stdout.split()[-1])

QRELS = {
    "dl19": "Data/qrels.eval.one.tsv",
    "dl20": "Data/qrels.eval.two.tsv",
    "dev":  "Data/qrels.dev.trec.tsv",
}

GRADED = {
    "MRR@10":   ["-l", "2", "-M", "10", "-m", "recip_rank"],
    "NDCG@10":  ["-m", "ndcg_cut.10"],
    "NDCG@100": ["-m", "ndcg_cut.100"],
    "MAP":      ["-l", "2", "-m", "map"],
}
BINARY = {
    "MRR@10": ["-M", "10", "-m", "recip_rank"],
    "MAP":    ["-m", "map"],
}

KS=list(range(10,101,10))
os.makedirs("Eval/ploteval",exist_ok=True)

for name,qrels in QRELS.items():
    measures = BINARY if name == "dev" else GRADED
    plt.figure(figsize=(8.5,4.5))
    for metric, flags in measures.items():
        values=[trecfairy(qrels, f"Runs/ksweep/rerank{k}_{name}.txt",flags) for k in KS]
        line, = plt.plot(KS, values, marker="o", label=metric)
        #not reranked
        base = trecfairy(qrels,f"Runs/bm25_{name}.txt",flags)
        plt.axhline(base, linestyle="--", color=line.get_color(),alpha=0.5)

        print(name, metric, "BM25:", round(base, 3), "by k:", [round(v, 3) for v in values])

    plt.title(f"{name}:rerank top-k bm25 results (dashed is bm25 only)")
    plt.xlabel("k (number of BM25 results reranked)")
    plt.ylabel("score")
    plt.xticks(KS)
    plt.grid(alpha=0.3)
    plt.legend(loc="center left",bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.savefig(f"Eval/ploteval/ksweep_{name}.png",dpi=150)
    plt.close()
    print("saved", f"Eval/ploteval/ksweep_{name}.png")


