#include <iostream>
#include "queryprocessor.hpp"
using namespace std;
void printFinish(const vector<ranked> &res, const string &query, IndexData &data)
{
    if (res.empty())
    {
        cout << "No results found";
    }

    vector<string> terms = clean_query(query);
    int rank = 1;
    for (auto &r : res)
    {
        cout << rank++ << ". docId:" << r.second << " score " << r.first << endl
             << snippetfairy(terms, getPassage(data, r.second)) << endl;
    }
}
int main()
{
    string query;
    IndexData data;
    loadIndexData(data, "lexicon.txt", "doc_length.bin", "collection.tsv");

    bool conjunctive = false;

    while (cout << "What are you searching for?" && getline(cin, query))
    {
        if (query == "/q")
            break;
        if (query == "/and")
        {
            conjunctive = true;
            continue;
        }
        if (query == "/or")
        {
            conjunctive = false;
            continue;
        }
        printFinish(search(query, conjunctive, data), query, data);
    }

    return 0;
}