#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdint>
#include <map>
#include <cctype>
#include <algorithm>
#include <optional>
#include <queue>
#include <filesystem>
#include <cstring>
#include <cerrno>
using namespace std;

const int BLOCK_SIZE = 128;
struct runRead // contains my identifying term
{
    string identTerm;           // ie. "magic"
    vector<pair<int, int>> res; // docId, freq
    int runIndex;               // which run file
};

struct compareRunRead
{
    bool operator()(const runRead &a, const runRead &b)
    {                                     // custom comparator for minHeap that makes it return the smallest identTerm at the top instead of the largest
        return a.identTerm > b.identTerm; // because priority queue would make sure the largest is on top and we want a min heap
    }
};
using MinHeap = priority_queue<runRead, vector<runRead>, compareRunRead>; // minHeap for runRead, including the comparator so we can use priority queue as a minheap

int getRunCount()
{ // need to pass runCount from indexer.cpp for the for-loop later on
    ifstream count_file("runs/run_count.txt");
    int runCount;
    count_file >> runCount; // read run count number
    count_file.close();
    return runCount;
}

pair<string, vector<pair<int, int>>> parseRunLine(const string &line) // parse line takes the identifying term in the runfile and returns something like {"identTerm",[(docId,freq)]}
{                                                                     // inverse of flushRun in indexer.cpp
    istringstream ss(line);
    string identTerm;
    ss >> identTerm; // what is the identifying term? ie. magic - take the identifying term

    vector<pair<int, int>> res; // res holds docId and frequency pairings
    int docId, freq;
    while (ss >> docId >> freq)
    {
        res.push_back({docId, freq}); // push pair into result vector
    }
    return {identTerm, res}; // res will be eg. {"magic", [(3,2)]}
}
vector<ifstream> opensRuns(int runCount) // i'm looking at all the run files ALL OF THEM
{
    vector<ifstream> runFiles; // keeping all of them open
    for (int i = 0; i < runCount; i++)
    {                                                                       // open every run file in binary mode
        ifstream runFile("runs/run_" + to_string(i) + ".bin", ios::binary); // opnes runfile with same logic from parser
        if (!runFile.is_open())
        {
            cerr << "Error opening file: runs/run_" << i << ".bin" << endl;
            cerr << "Merger is running in: " << filesystem::current_path() << endl;
            cerr << "File exists from here? " << filesystem::exists("runs/run_" + to_string(i) + ".bin") << endl;
            cerr << "Reason: " << strerror(errno) << endl;
            exit(1);
        }
        runFiles.push_back(std::move(runFile)); // no heavy dupes with move also i can't copy files if it's in an ifstream
    }
    return runFiles;
}

optional<runRead> readNextLine(ifstream &runFile, int runIndex) // optional bc might return a value but also might return nothing
{                                                               // reads unconsumed line from specific run file, parses via parseRunLine
    string line;
    if (getline(runFile, line))
    {
        auto [identTerm, res] = parseRunLine(line);
        return runRead{identTerm, res, runIndex};
    }
    return nullopt; // no more lines in run file to read
}

MinHeap initializeHeap(int runCount, vector<ifstream> &runFiles)
{ // calls readNextLine once per open run file to seed the heap with everyone's first front, takes place before main merge
    MinHeap minHeap;
    for (int i = 0; i < runCount; i++)
    {
        auto entry = readNextLine(runFiles[i], i); // for every file
        if (entry.has_value())
        {
            minHeap.push(entry.value());
        }
    }
    return minHeap; // heap holds the first line of every run, alphabetically smallest on top
}

vector<pair<int, int>> mergePostingsForTerm(const vector<runRead> &matched)
{ // merge every result in2 1 for specific term ie. "magic"
    vector<pair<int, int>> merged;
    for (auto &entry : matched) // matched looks like: identTerm ie. "magic", [docid,freq],which file are we looking at
    {
        merged.insert(merged.end(), entry.res.begin(), entry.res.end());
    }
    sort(merged.begin(), merged.end());

    return merged; // sorted in docID order ie. [(0,1), (15,2), (5000012,1)]
}
vector<runRead> matchingTerms(MinHeap &minHeap)
{ // find all matching terms across runfiles, return in single vector using our minHeap
    vector<runRead> matched;
    string matchTerm = minHeap.top().identTerm; // this is the term i'm looking for

    while (!minHeap.empty() && minHeap.top().identTerm == matchTerm)
    {
        matched.push_back(minHeap.top());
        minHeap.pop(); // keep popping until it's not that term anymore
    }

    return matched;
}

void varbyteEncode(uint32_t n, vector<uint8_t> &encoded)
{
    while (n >= 128)                                              // if it's a small number, less than 128 which is 2 bytes, i'll just store it
    {                                                             // defined max varbyte size at 128
        encoded.push_back(static_cast<uint8_t>((n & 127) | 128)); // n&127 keeps lowest 7 bits of n
        n >>= 7;                                                  // keeps one byte in for continuation flag, shift to the right for next 7
    }
    encoded.push_back(static_cast<uint8_t>(n)); // fits 7 bits, end of number
}

uint32_t decodevar(const vector<uint8_t> &encoded, size_t &pos)
{
    uint32_t n = 0; // holding decoded val
    int shift = 0;
    while (true)
    {
        uint8_t curr = encoded[pos++];
        n |= static_cast<uint32_t>(curr & 127) << shift; // take each byte's 7 data bits and shift them back but without flag
        if (!(curr & 128))
        {
            break;
        } // zero flag
        shift += 7;
    }
    return n;
}
void writeu32(ofstream &encoded, uint32_t b)
{ // 32 bits = 4 bytes
    encoded.write(reinterpret_cast<const char *>(&b), sizeof(b));
}
void writeTermEntry(ofstream &indexFile, ofstream &lexFile, const string &term, const vector<pair<int, int>> &postings) // we store docId gaps which are smaller
{                                                                                                                       // TERM them where does it start? what is the offset? how many documents does it appear in
    uint64_t offset = indexFile.tellp(); // where is the pointer now
    size_t df = postings.size(); // how many documents does this term appear in
    size_t numBlocks = (df + BLOCK_SIZE - 1) / BLOCK_SIZE; // how many blocks of 128 are needed to hold these postings -> we round up in C++

    vector<uint32_t> lastDocIDs, docSizes, freqSizes;
    vector<uint8_t> payload; // all my compressed data for one term ie. [block 0 gaps][block 0 freqs]
    uint32_t prev = 0; // carries across blocks

    for (size_t b = 0; b < numBlocks; b++)
    {
        size_t start = b * BLOCK_SIZE;
        size_t end = min(start + BLOCK_SIZE, df); // which one is smaller 
        vector<uint8_t> docBytes, freqBytes; // docbytes is one block's docid gaps
        for (size_t i = start; i < end; i++)
        {
            uint32_t docID = static_cast<uint32_t>(postings[i].first);
            varbyteEncode(docID - prev, docBytes); // stores gaps not docId
            varbyteEncode(static_cast<uint32_t>(postings[i].second), freqBytes); // stores the frequency too
            prev = docID;
        }
        lastDocIDs.push_back(prev); // previous docid
        docSizes.push_back(docBytes.size()); // how many bytes this block's gaps take up 
        freqSizes.push_back(freqBytes.size());
        payload.insert(payload.end(), docBytes.begin(), docBytes.end());
        payload.insert(payload.end(), freqBytes.begin(), freqBytes.end());
    }

    writeu32(indexFile, numBlocks);
    for (size_t b = 0; b < numBlocks; b++)
    {
        writeu32(indexFile, lastDocIDs[b]);
        writeu32(indexFile, docSizes[b]);
        writeu32(indexFile, freqSizes[b]); // docsize+freq size tells me when I can go to the next block
    }
    indexFile.write(reinterpret_cast<const char *>(payload.data()), payload.size());

    uint64_t length = static_cast<uint64_t>(indexFile.tellp()) - offset; // position in index.bin - offset=how much space header and payload take up
    lexFile << term << ' ' << offset << ' ' << length << ' ' << df << '\n'; // "magic" 
}
void runMerge(MinHeap &minHeap, vector<ifstream> &runFiles, ofstream &indexFile, ofstream &lexFile) // handles one term per cycle ie. "magic" in one run, "model" in the next
{
    while (!minHeap.empty())
    {
        vector<runRead> matched = matchingTerms(minHeap);              // everything on the heap for this term.
        string term = matched[0].identTerm;                            // what term was that? ie. "magic"
        vector<pair<int, int>> merged = mergePostingsForTerm(matched); // combine every run's posting for this one term into a vector
        writeTermEntry(indexFile, lexFile, term, merged);              // write to index.bin and lexicon.txt

        for (auto &entry : matched)
        {
            auto next = readNextLine(runFiles[entry.runIndex], entry.runIndex);
            if (next.has_value())
                minHeap.push(next.value()); // push from run files onto heap
        }
    }
}
int main()
{
    int runCount = getRunCount();
    vector<ifstream> runFiles = opensRuns(runCount);
    MinHeap minheap = initializeHeap(runCount, runFiles);

    ofstream indexFile("index.bin", ios::binary);
    ofstream lexFile("lexicon.txt");
    if (!lexFile || !indexFile)
    {
        cerr << "Failed to open output files." << endl;
        return 1;
    }

    runMerge(minheap, runFiles, indexFile, lexFile);
    cout << "Merge complete" << endl;

    return 0;
}