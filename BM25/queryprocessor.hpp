#include <iostream>
#include <string>
#include <algorithm>
#include <cctype>
#include <vector>
#include "startup.h"
#include <cmath> // for log
#include <memory>
#include <sstream>
#include <queue>
using namespace std;
using ranked = pair<double, uint32_t>; // score and docid - for minheap so it will

struct BestRes
{
    size_t limit;                                                     // what is the number of res u want to return
    priority_queue<ranked, vector<ranked>, greater<ranked>> minheap2; // keeping worst score on top so I can throw it away when I need to

    void filling(uint32_t docID, double rank)
    {
        if (minheap2.size() < limit) // how many did you want
        {
            minheap2.push({rank, docID});
        }
        else if (rank > minheap2.top().first) // only if it's better than the current worst
        {
            minheap2.pop();               // remove worst score
            minheap2.push({rank, docID}); // add new worst score - but still better than initial worst
        }
    }

    vector<ranked> bestofbest()
    {
        vector<ranked> result;
        while (!minheap2.empty())
        {
            result.push_back(minheap2.top()); // fill with minheap2 worst to best
            minheap2.pop();
        }
        reverse(result.begin(), result.end()); // now best to worst whee
        return result;
    }
};

vector<string> tokens(string text) // from indexer
{
    vector<string> token_list;
    for (auto &c : text)
    {
        if (ispunct(static_cast<unsigned char>(c)) && c != '\'')
            c = ' '; // punctuation becomes a space, so words stay separate - solves problem where our words were getting merged
    }
    for (auto &i : text)
    { // lowercase all characters
        i = tolower(static_cast<unsigned char>(i));
    }
    stringstream ss(text);
    string token;
    while (ss >> token)
    {
        // Remove apostrophes at bginning and end because we don't want 'hello'
        while (!token.empty() && token.front() == '\'')
        {
            token.erase(0, 1); // starting at position 0, remove 1 character
        }
        while (!token.empty() && token.back() == '\'')
        {
            token.pop_back();
        }
        if (token.empty())
            continue; // skips all empty tokens
        token_list.push_back(token);
    }
    return token_list;
}
vector<string> clean_query(const string &query)
{
    vector<string> terms;
    for (auto &t : tokens(query))
    { // runs tokenizer on query and cleans it
        if (find(terms.begin(), terms.end(), t) == terms.end())
        {                       // searches terms for curr t
            terms.push_back(t); // only pushes back if no duplicate terms
        }
    }
    return terms; // yay no dupes
}

double inversedocfreq(int docfreq, uint32_t numDocs)
{
    return log((numDocs - docfreq + 0.5) / (docfreq + 0.5) + 1.0); // we are calculating the rarity of the term by taking the no. of docs it DOESN'T appear in / the number of docs it DOES appear in
}

double ranking(uint32_t termfreq, uint32_t document_length, double avgdoclength, double idocfreq)
{
    const double k1 = 1.2, b = 0.75;                                      // term saturation - k1 helps with this / b helps with penalizing long docs favor short ones
    double norm = k1 * (1.0 - b + b * document_length / avgdoclength);    // penalize long documents slightly
    double bm25 = idocfreq * (termfreq * (k1 + 1.0)) / (termfreq + norm); // rare words matter more
    return bm25;
}
// AND
vector<ranked> conjunctiveDAAT(double averageDocLength, const vector<uint32_t> &documentLengths, const vector<string> &terms, const map<string, LexEntry> &lexicon, size_t limit, uint32_t numDocs, const string &indexFile = "index.bin")
{ // only documents with BOTH
    // start daat process
    BestRes res{limit};
    vector<unique_ptr<InvertedList>> lists;
    for (const string &t : terms)
    {
        auto lp = make_unique<InvertedList>(); // opening one list per term - also smart pointer
        if (!lp->open(t, lexicon, indexFile))
        {
            for (auto &l : lists)
            {
                l->close(); // close all the files i've opened if I can't find in lexicon
            }
            return {};
        }
        lists.push_back(std::move(lp)); // or elsei'm p
    }
    if (lists.empty())
    {
        return {};
    }

    // begin w shortest list
    sort(lists.begin(), lists.end(), [](const unique_ptr<InvertedList> &a, const unique_ptr<InvertedList> &b)
         {
             return a->getDF() < b->getDF(); // custom comparator to give shortest list first
             // getdf refers to the number of documents that contain that specific term so return the list with the fewest documents first
         });

    vector<double> inverteddocfreqs;

    for (auto &x : lists)
    {
        inverteddocfreqs.push_back(inversedocfreq(x->getDF(), numDocs));
    }

    uint32_t currdocno = 0;
    while (true)
    {
        currdocno = lists[0]->nextGEQ(currdocno); // get next docid from shortest list

        if (currdocno == NOT_FOUND)
        {
            break;
        } // but check

        uint32_t d = currdocno;

        for (size_t i = 1; i < lists.size() && (d = lists[i]->nextGEQ(currdocno)) == currdocno; i++) // check if d==currdocno aka if this list contains this docid
        {
        }
        if (d == NOT_FOUND)
            break;
        if (d > currdocno)
        { // move to the next docid bc it's not in every list
            currdocno = d;
            continue;
        }

        // score
        double score = 0.0;
        for (size_t i = 0; i < lists.size(); i++)
        {
            score += ranking(lists[i]->getFreq(), documentLengths[currdocno], averageDocLength, inverteddocfreqs[i]);
        }
        res.filling(currdocno, score); // add to minheap
        currdocno++;                   // next docid
    }

    for (auto &x : lists)
    {
        x->close();
    }
    return res.bestofbest(); // return the best results
}

// OR
bool terminatedisjunctive(const vector<uint32_t> &documents)
{
    for (uint32_t x : documents)
    {
        if (x != NOT_FOUND)
        {
            return false;
        }
    }
    return true;
}
vector<ranked> disjunctiveDAAT(double averageDocLength, const vector<uint32_t> &documentLengths, const vector<string> &terms, const map<string, LexEntry> &lexicon, size_t limit, uint32_t numDocs, const string &indexFile = "index.bin")
{ // we take the smallest number so we don't skip 
    vector<unique_ptr<InvertedList>> lists; // visit every number that appears on ANY list
    vector<double> idocfreqs;
    for (auto &t : terms)
    {
        auto list = make_unique<InvertedList>();
        if (!list->open(t, lexicon, indexFile))
            continue; // not in index, so skip ahead
        idocfreqs.push_back(inversedocfreq(list->getDF(), numDocs)); // for ranking
        lists.push_back(std::move(list));
    }

    BestRes res{limit};

    uint32_t currdocno = 0;
    while (true)
    {
        vector<uint32_t> documents;
        for (auto &l : lists)
        {
            documents.push_back(l->nextGEQ(currdocno));
        }
        if (terminatedisjunctive(documents))
        {
            break;
        }
        currdocno = *min_element(documents.begin(), documents.end()); // get the smallest docid

        double score = 0.0;
        for (size_t i = 0; i < lists.size(); i++)
        {
            if (documents[i] == currdocno)
            { // for this particular document
                score += ranking(lists[i]->getFreq(), documentLengths[currdocno], averageDocLength, idocfreqs[i]);
            }
        }
        res.filling(currdocno, score); // add to minheap
        currdocno++;                   // next docid
    }
    for (auto &l : lists)
    {
        l->close();
    }

    return res.bestofbest(); // return the best results
}

vector<ranked> search(const string &query, bool conjunctive, IndexData &data, size_t limit = 10, const string &indexFile = "index.bin")
{
    vector<string> terms = clean_query(query); // clean query and tokenize
    if (terms.empty())
        return {};
    if (conjunctive)
    {
        return conjunctiveDAAT(data.averageDocLength, data.documentLengths, terms, data.lexicon, limit, data.numDocs, indexFile);
    }
    else
    {
        return disjunctiveDAAT(data.averageDocLength, data.documentLengths, terms, data.lexicon, limit, data.numDocs, indexFile);
    }
}
string snippetfairy(const vector<string> &terms, const string &document)
{
    string lower = document; // we are looking for terms, so we have to make everything lowercase or it won't match

    transform(lower.begin(), lower.end(), lower.begin(), // start, end, where do you start writing
              [](unsigned char c)
              { return tolower(c); }); // 4 args

    vector<size_t> positions;

    for (auto &t : terms)
    {
        size_t position = lower.find(t); // mapping where these terms are - string acts like array...

        if (position != string::npos)
        { // found
            positions.push_back(position);
        }
    }

    if (positions.empty())
    { // just show beginning
        return document.substr(0, 200);
    }

    size_t first = *min_element(positions.begin(), positions.end()); // first position in document
    size_t last = *max_element(positions.begin(), positions.end());  // last position

    size_t start = (first < 100) ? 0 : first - 100;
    size_t end = min(last + 100, document.size());
    size_t sniplim = min(end - start, size_t(200));

    string snip = document.substr(start, sniplim);
    replace(snip.begin(), snip.end(), '\n', ' ');

    return snip;
}
