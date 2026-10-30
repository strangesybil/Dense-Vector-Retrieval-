# HW3 Notes

## Setup
- Machine: (e.g. MacBook Air M2, 16 GB RAM)
- Collection: 1,000,000 passages (MS MARCO subset)
- Query sets: DL 2019 (43 queries), DL 2020 (54), Dev (1,000)
- Query text: queries.eval.tsv / queries.dev.tsv from MS MARCO queries.tar.gz (not on Drive)

## System 1: BM25 (C++)
Parameters: k1 = 1.2, b = 0.75, disjunctive (OR) DAAT, top 1000

### Index build
| Step    | Time  | Notes  |
|---------|-------|--------|
| Indexer | ___ s | 9 runs |
| Merger  | ___ s |        |

### Index size (disk)
| File           | Size    |
|----------------|---------|
| index.bin      | 104 MB  |
| lexicon.txt    | 13 MB   |
| doc_length.bin | 3.8 MB  |
| docid_map.bin  | 7.6 MB  |
| Total          | ~128 MB |

- Index load time: ___ s
- Memory while running (Activity Monitor): ___ MB

### Query latency
| Query set | Queries | Avg (ms) | p95 (ms) | Results written |
|-----------|---------|----------|----------|-----------------|
| DL 2019   | 43      |  130.481 |  234.002 | 43,000          |
| DL 2020   | 54      |  112.788 |  265.428 | 54,000          |
| Dev       | 1,000   |   124.3  |  277.731 | 998,274         |

Run files: Runs/bm25_dl19.txt, Runs/bm25_dl20.txt, Runs/bm25_dev.txt

## System 3: BM25 + dense re-ranking (Python)
| Candidates | Embedding load time | Avg re-rank time (ms) | p95 (ms) |
|------------|---------------------|-----------------------|----------|
| Top 100    |                     |                       |          |
| Top 1000   |                     |                       |          |

Note: total latency per query = BM25 time + re-rank time.

## System 2: HNSW (Nouf)
| M | efConstruction | efSearch | Build time | RAM | Avg (ms) | p95 (ms) |
|---|----------------|----------|------------|-----|----------|----------|
| 4 | 50             | 50       |            |     |          |          |
| 8 | 100            | 100      |            |     |          |          |
| 8 | 200            | 200      |            |     |          |          |

## Results (from trec_eval)
### DL 2019
| System        | MRR@10 | Recall@100 | NDCG@10 | NDCG@100 |
|---------------|--------|------------|---------|----------|
| BM25          |        |            |         |          |
| HNSW (best)   |        |            |         |          |
| Re-rank @100  |        |            |         |          |
| Re-rank @1000 |        |            |         |          |

### DL 2020
(same table)

### Dev
| System        | MRR@10 | Recall@100 | MAP |
|---------------|--------|------------|-----|
| BM25          |        |            |     |
| HNSW (best)   |        |            |     |
| Re-rank @100  |        |            |     |
| Re-rank @1000 |        |            |     |

## Observations (for the report)
- Dev queries touch most of the 1M docs because of common words ("what", "is"), which makes BM25 OR search slow
-