import sys

subset_path, collection_path, out_path=sys.argv[1:4]

with open(subset_path) as f: # open subset and look at pids, keep in set
    keep = {line.split("\t")[0].strip() for line in f if line.strip()}

kept = 0

with open(collection_path, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout: 
    for line in fin: 
        pid=line.split("\t",1)[0] #so it stops searching after finding the first tab
        if pid in keep: #only going to keep pids that are matching
            fout.write(line) 
            kept+=1

print(f"subset ids: {len(keep)}, passages kept: {kept}")