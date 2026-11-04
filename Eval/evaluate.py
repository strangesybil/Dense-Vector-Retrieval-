import subprocess
import os
from unittest import result

trec_evaluation="../trec_eval/trec_eval"
def trec(flags, qrels, run):
    result=subprocess.run(
        [trec_evaluation] + flags + [qrels, run_file],
        capture_output=True, text=True,
)
    if not result.stdout.strip():
        print("trec_eval failed on ", run_file," with ",flags)
        print(result.stderr)
        exit(1)
    return float(result.stdout.split()[-1])
qrels = {
    "dl19": "Data/qrels.eval.one.tsv",
    "dl20": "Data/qrels.eval.two.tsv",
    "dev": "Data/qrels.dev.trec.tsv",
}

graded = {
    "MRR@10": ["-l", "2", "-M", "10", "-m", "recip_rank"],
    "Recall@100": ["-l", "2", "-m", "recall.100"],
    "NDCG@10": ["-m", "ndcg_cut.10"],
    "NDCG@100": ["-m", "ndcg_cut.100"]
}

BINARY = {
    "MRR@10": ["-M","10","-m","recip_rank"],
    "Recall@100": ["-m","recall.100"],
    "MAP":["-m","map"]
}

systems={
    "bm25": "Runs/bm25_{name}.txt",
    "rerank @100": "Runs/rerank100_{name}.txt",
    "rerank @1000": "Runs/rerank1000_{name}.txt"
}

for name, qrels in qrels.items():
    measures=BINARY if name=="dev" else graded 
    print(f"\n### {name}")
    print("| System |" + " | ".join(measures) + "|")
    print("|---"*(len(measures)+1)+"|")

    for system, pattern in systems.items():
        run_file=pattern.format(name=name)
        if not os.path.exists(run_file):
            continue
        scores=[trec(flags,qrels,run_file) for flags in measures.values()]
        print(f"| {system} | " + " | ".join(f"{s:.3f}" for s in scores) + " |")