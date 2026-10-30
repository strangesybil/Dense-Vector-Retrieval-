import h5py
import numpy as np
import time


PASSAGE_H5 = "Data/msmarco_passages_embeddings_subset.h5"
QUERY_H5   = "Data/msmarco_queries_dev_eval_embeddings.h5"

def load_h5_embeddings(file_path,id_key="id",embedding_key="embedding"):
    print(f"Loading data from {file_path}...")
    with h5py.File(file_path, 'r') as f:
        ids = np.array(f[id_key]).astype(str) #turn to string
        embeddings = np.array(f[embedding_key]).astype(np.float32)  #turn to float 32 bit decimals
    print(f"Loaded {len(ids)} embeddings.")
    return ids, embeddings
    
pids, pemb=load_h5_embeddings(PASSAGE_H5)
qids, qemb=load_h5_embeddings(QUERY_H5)

pidrows={pids: i for i,pids in enumerate(pids)}
qidrows={qids: i for i,qids in enumerate(qids)}

print("passage embeddings: ",pemb.shape)
print("passages in lookup: ", len(pidrows))

def rerank(name,k):
    run_file=f"Runs/bm25_{name}.txt"
    candidates={}
    with open(run_file) as f: 
        for line in f: 
            qid, _, pid, rank, score, func=line.split()
            if(int(rank)>k):
                continue
            
            candidates.setdefault(qid,[]).append(pid)
    reranked = {}
    import time
    latencies = []

    for qid, cand_pids in candidates.items():
        t0=time.perf_counter()
        query_vector=qemb[qidrows[qid]]
        rows=[pidrows[p] for p in cand_pids]
        candidate_vector=pemb[rows]
        scores=candidate_vector@query_vector #create dot product
        order=np.argsort(-scores) # in depreciating order
        reranked[qid]=[(cand_pids[i],scores[i]) for i in order]
        latencies.append((time.perf_counter()-t0)*1000) # milliseconds
    
    OUT = f"Runs/rerank{k}_{name}.txt"
    with open(OUT,"w") as outfile:
        for qid,res in reranked.items():
            for rank,(pid,score) in enumerate(res,start=1):
                outfile.write(f"{qid} Q0 {pid} {rank} {score:.6f} RERANK\n")
    print(f"{name} k={k}: {len(candidates)} queries, "
        f"avg {np.mean(latencies):.3f} ms, p95 {np.percentile(latencies, 95):.3f} ms")


for name in ["dl19","dl20","dev"]:
    for k in [100,1000]:
        rerank(name,k)