import h5py, numpy as np, time, os
os.makedirs("Runs/ksweep", exist_ok=True)

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

pidrows={pids: i for i,pids in enumerate(pids)} #create row numbers so i can find a passage's vector
qidrows={qids: i for i,qids in enumerate(qids)}

print("passage embeddings: ",pemb.shape)
print("passages in lookup: ", len(pidrows))

def rerank(name,k,out="Runs"):
    run_file=f"Runs/bm25_{name}.txt"
    bm25={}
    with open(run_file) as f: 
        for line in f: 
            qid, _, pid, rank, score, func=line.split()
            bm25.setdefault(qid,[]).append(pid) #retrieve key value IF it ecists 
    final = {}
    import time
    latencies = []

    for qid, allpids in bm25.items():
        top=allpids[:k] # i only wanna rerank k 
        rest=allpids[k:] #idc about these
        t0=time.perf_counter() #start timer for latency measrement
        query_vector=qemb[qidrows[qid]] #which row holds that query, then qemb shows what it means
        rows=[pidrows[p] for p in top] #passage id to row number in the section we r looking for (top k)
        scores=pemb[rows] @ query_vector #matrix multiplication for dot product - can't do loop
        order=np.argsort(-scores) #sort them in descending order
        reranked=[top[i] for i in order]
        latencies.append((time.perf_counter()-t0)*1000) #convert to ms 
        final[qid]=reranked+rest
    
    OUT = f"{out}/rerank{k}_{name}.txt"
    with open(OUT,"w") as outfile:
        for qid,pids_list in final.items():
            n=len(pids_list)
            for rank,pid in enumerate(pids_list,start=1):
                outfile.write(f"{qid} Q0 {pid} {rank} {n-rank+1} RERANK\n") #trec format
    print(f"{name} k={k}: {len(bm25)} queries, "
        f"avg {np.mean(latencies):.3f} ms, p95 {np.percentile(latencies, 95):.3f} ms")


for name in ["dl19","dl20","dev"]:
    for k in range(10,101,10):
        rerank(name,k,out="Runs/ksweep")