import subprocess
import os
import numpy as np
from rerank_k import read_qrels, read_run, get_scores

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")  # the repo folder
RUNS = os.path.join(ROOT, "Runs")


def find(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# trec_eval is in a folder next to the repo folder (or inside it)
trec_evaluation = find([
    os.path.join(ROOT, "..", "trec_eval", "trec_eval"),
    os.path.join(ROOT, "trec_eval", "trec_eval"),
    os.path.join(ROOT, "..", "trec_eval", "trec_eval.exe"),
    os.path.join(ROOT, "trec_eval", "trec_eval.exe"),
])
if trec_evaluation is None:
    print("trec_eval not found, using the python metrics instead (they match trec_eval up to rounding)")


def trec(flags, qrels_file, run_file):
    result = subprocess.run(
        [trec_evaluation] + flags + [qrels_file, run_file],
        capture_output=True, text=True,
    )
    if not result.stdout.strip():
        print("trec_eval failed on ", run_file, " with ", flags)
        print(result.stderr)
        exit(1)
    return float(result.stdout.split()[-1])


def python_scores(qrels_file, run_file, level):
    # MRR@10, NDCG@10, MAP, Recall@100, NDCG@100 averaged over the queries
    rels = read_qrels(qrels_file)
    run = read_run(run_file)
    all_scores = []
    for qid, docs in run.items():
        if qid not in rels:
            continue
        s = get_scores(docs, rels[qid], level)
        if s is None:
            continue
        r = rels[qid]
        found = len([d for d in docs[:100] if r.get(d, 0) >= level])
        recall = found / len([g for g in r.values() if g >= level])
        gains = [r.get(d, 0) for d in docs[:100]]
        best = sorted(r.values(), reverse=True)[:100]
        dcg = sum(g / np.log2(i + 2) for i, g in enumerate(gains))
        idcg = sum(g / np.log2(i + 2) for i, g in enumerate(best))
        all_scores.append(list(s) + [recall, dcg / idcg])
    return np.mean(all_scores, axis=0)


def find_qrels(filename):
    return find([os.path.join(ROOT, "Data", filename), os.path.join(ROOT, "HNSW", filename)])


qrels = {
    "dl19": find_qrels("qrels.eval.one.tsv"),
    "dl20": find_qrels("qrels.eval.two.tsv"),
    "dev": find_qrels("qrels.dev.trec.tsv"),
}

# the dev qrels are qid pid rel but trec_eval needs qid 0 pid rel, so make that file if its not there
if qrels["dev"] is None:
    plain = find_qrels("qrels.dev.tsv")
    if plain is not None:
        qrels["dev"] = os.path.join(os.path.dirname(plain), "qrels.dev.trec.tsv")
        with open(qrels["dev"], "w") as out:
            for line in open(plain):
                parts = line.split()
                out.write(f"{parts[0]} 0 {parts[-2]} {parts[-1]}\n")

# dl19 and dl20 have grades 0-3, MRR / MAP / recall only count grade 2 and up
graded = {
    "MRR@10": ["-l", "2", "-M", "10", "-m", "recip_rank"],
    "NDCG@10": ["-m", "ndcg_cut.10"],
    "MAP": ["-l", "2", "-m", "map"],
    "Recall@100": ["-l", "2", "-m", "recall.100"],
    "NDCG@100": ["-m", "ndcg_cut.100"]
}

# dev is just 0/1
BINARY = {
    "MRR@10": ["-M", "10", "-m", "recip_rank"],
    "NDCG@10": ["-m", "ndcg_cut.10"],
    "MAP": ["-m", "map"],
    "Recall@100": ["-m", "recall.100"]
}

# a system with no run file is skipped
systems = {
    "bm25": "bm25_{name}.txt",
    "rerank @100": "rerank100_{name}.txt",
    "rerank @1000": "rerank1000_{name}.txt",
    "hnsw (4,50,50)": "hnsw_m4_ef50_{name}.txt",
    "hnsw (8,100,100)": "hnsw_m8_ef100_{name}.txt",
    "hnsw (8,200,200)": "hnsw_m8_ef200_{name}.txt",
    "flat (exact)": "flat_{name}.txt",
    "rrf (bm25 + hnsw)": "rrf_{name}.txt"
}

for name, qrels_file in qrels.items():
    measures = BINARY if name == "dev" else graded
    print(f"\n### {name}")
    if qrels_file is None:
        print("cant find the qrels for this set, skipping")
        continue
    print("| System | " + " | ".join(measures) + " |")
    print("|---" * (len(measures) + 1) + "|")

    for system, pattern in systems.items():
        run_file = os.path.join(RUNS, pattern.format(name=name))
        if not os.path.exists(run_file):
            continue
        if trec_evaluation is not None:
            scores = [trec(flags, qrels_file, run_file) for flags in measures.values()]
        else:
            level = 1 if name == "dev" else 2
            scores = python_scores(qrels_file, run_file, level)[:len(measures)]
        print(f"| {system} | " + " | ".join(f"{s:.3f}" for s in scores) + " |")