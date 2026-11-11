**BM25 Ranking**
Set up: ./BM25/query
Shows: Top 10 with passage IDs and rankings (built on 1M subset)

**batch.cpp(how the run files are produced)** 
Type: ./BM25/batch Data/queries.eval.tsv Data/qrels.eval.one.tsv Runs/bm25_dl19.txt
then: head -3 Runs/bm25_dl19.txt

**Reranking**
Type: python Rerank/rerank.py