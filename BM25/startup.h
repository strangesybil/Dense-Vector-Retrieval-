#include "inverlist.h"
#ifndef STARTUP_H
#define STARTUP_H

struct IndexData
{
    map<string, LexEntry> lexicon;
    double averageDocLength;
    vector<uint32_t> documentLengths;
    uint32_t numDocs = 0;
    vector<uint64_t> passageOffset; // snippet
    ifstream collect;               // snippet
    vector<string> pids;
};

void docTable(const string &filename, IndexData &data)
{

    ifstream f(filename, ios::binary); // read doctable
    if (!f)
    {
        cerr << "Could not open" << filename << endl;
        exit(1);
    }

    uint64_t totalLength = 0;
    uint32_t length;
    while (f.read(reinterpret_cast<char *>(&length), sizeof(length))) // 4 byte chunks
    {

        data.documentLengths.push_back(length); // what is the position in the file for this doc
        totalLength += length;
        data.numDocs++;
    }

    data.averageDocLength = double(totalLength) / data.numDocs;
}

void passaget(const string &filename, IndexData &data) // where does each line start - to help snippet
{
    uint64_t bytecounter = 0;
    ifstream f(filename, ios::binary); // don't change file endings in binary mode, don't wanna throw off byte count
    if (!f)
    {
        cerr << "Could not open " << filename << endl;
        exit(1);
    }
    string line;

    while (data.passageOffset.size() < data.numDocs && getline(f, line))
    {
        data.passageOffset.push_back(bytecounter);
        data.pids.push_back(line.substr(0, line.find('\t')));
        bytecounter += line.size() + 1;
    }
    data.collect.open(filename, ios::binary);
}
void loadIndexData(IndexData &data, const string &lexFile, const string &lenFile, const string &collFile)
{
    data.lexicon = loadLexicon(lexFile);
    docTable(lenFile, data);
    passaget(collFile, data);
}

string getPassage(IndexData &data, uint32_t docId)
{
    if (docId >= data.passageOffset.size())
        return "";
    data.collect.clear();
    data.collect.seekg(data.passageOffset[docId]);
    string line;
    getline(data.collect, line);
    size_t tab = line.find('\t'); // where does the line start
    string text;
    if (tab == string::npos)
    { // fouund tab
        text = line;
    }
    else
    {
        text = line.substr(tab + 1);
    }
    if (!text.empty() && text.back() == '\r')
    {
        text.pop_back();
    }

    return text;
}

#endif