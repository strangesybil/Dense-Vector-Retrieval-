// read in command line arguments
// Read the qrels file into a set of query IDs
// Load the index
// Read the query file and pick out the wanted queries
// Run the search and write the run file
// Add timing

#include "queryprocessor.hpp"
#include <fstream>
#include <unordered_set>
#include <chrono>
#include <iomanip>
#include <string>
#include <sstream>
#include <iostream>
#include <chrono>
using namespace std;

int main(int argc, char **argv)
{
    unordered_set<string> wanted;
    if (argc != 4)
    {
        cerr << "Error with number of arguments. Try again.";
    }
    string queriesPath = argv[1]; // from queries.eval.tsv
    string qrelsPath = argv[2];   // qrels.eval.one.tsv
    string outPath = argv[3];     // writing to bm25_d1l9
    size_t k;                     // number of results per query
    if (argc > 4)
    {
        k = stoull(argv[4]); // turning it into a number
    }
    else
    {
        k = 1000; // how big the vector is
    }

    cerr << "queries: " << queriesPath << endl;
    cerr << "qrels: " << qrelsPath << endl;
    cerr << "out " << outPath << endl;
    cerr << "k :" << k << endl;

    ifstream file(qrelsPath);
    string line;

    if (!file)
    {
        cerr << "Could not open " << qrelsPath << endl;

        return 1;
    }

    while (getline(file, line))
    {
        istringstream ss(line);
        string qid;
        if (ss >> qid)
        {                       // rmb ss reads until first whitespace
            wanted.insert(qid); // puts all relevant (43) queries into a set so lookups are instant
        }
    }

    cout << "Query ids in qrels: " << wanted.size() << endl; // check which ones

    IndexData data;

    loadIndexData(data, "Built files/lexicon.txt", "Built files/doc_length.bin", "Data/new.tsv");

    cout << data.numDocs << endl; // number of documents in the index

    ifstream queries(queriesPath);
    if (!queries)
    {
        cerr << "Could not open " << queriesPath << endl;
        return 1;
    }
    ofstream out(outPath);
    if (!out)
    {
        cerr << "Could not open " << outPath << " to write" << endl;
        return 1;
    }
    string line2;
    int count = 0;
    vector<double> latencies;
    while (getline(queries, line2))
    {
        if (!line2.empty() && line2.back() == '\r') // because i don't wanna drop the last word and this file was made on windows
        {
            line2.pop_back();
        }
        size_t tab = line2.find('\t');
        if (tab == string::npos)
        {
            continue;
        }
        string qid = line2.substr(0, tab);    // what happens before tab
        string text = line2.substr(tab + 1);  // what happens after the tab
        if (wanted.find(qid) == wanted.end()) // these are not the droids you are looking for
        {                                     // not a judged query, skip
            continue;
        }
        auto t0 = chrono::steady_clock::now(); // timing the search
        vector<ranked> res = search(text, false, data, k);
        auto t1 = chrono::steady_clock::now();
        double ms = chrono::duration<double, milli>(t1 - t0).count();
        latencies.push_back(ms);
        int rank = 1;
        for (auto &r : res)
        {
            out << qid << " Q0 " << data.pids[r.second] << " " << rank << " " << r.first << " BM25\n"; // r.second is the internal doc number -> turn into a real pid + r.first is bm25 score
            rank++;
        }
        count++;
    }

    cerr << count << endl;

    sort(latencies.begin(), latencies.end());
    double total = 0;
    for (double ms : latencies)
        total += ms;                                                                          // calculate total time
    cerr << "Average latency " << total / latencies.size() << " milliseconds " << endl;       // average time per query
    cerr << "P95 Latency " << latencies[latencies.size() * 0.95] << " milliseconds " << endl; // 95th percentile latency -> catch the slow cases

    return 0;
}