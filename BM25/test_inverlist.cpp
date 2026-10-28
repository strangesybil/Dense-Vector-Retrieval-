#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include "inverlist.h"
using namespace std;

int passed = 0, failed = 0;

void check(bool ok, const string &msg)
{
    if (ok)
        passed++;
    else
    {
        failed++;
        cout << "FAIL: " << msg << endl;
    }
}

// pulls a term's postings straight from the run files
vector<pair<int, int>> getRaw(const string &term)
{
    vector<pair<int, int>> raw;
    ifstream countFile("runs/run_count.txt");
    int runCount = 0;
    countFile >> runCount;

    for (int i = 0; i < runCount; i++)
    {
        ifstream run("runs/run_" + to_string(i) + ".bin");
        string line;
        while (getline(run, line))
        {
            istringstream ss(line);
            string t;
            ss >> t;
            if (t != term)
                continue;
            int d, f;
            while (ss >> d >> f)
                raw.push_back({d, f});
        }
    }
    sort(raw.begin(), raw.end());
    return raw;
}

// jumps to every step-th posting and checks docID and freq
bool seekTest(const string &term, const map<string, LexEntry> &lexicon,
              const vector<pair<int, int>> &raw, int step)
{
    InvertedList list;
    list.open(term, lexicon);
    for (size_t k = 0; k < raw.size(); k += step)
    {
        uint32_t target = (k == 0) ? 0 : raw[k - 1].first + 1;
        if (list.nextGEQ(target) != (uint32_t)raw[k].first ||
            list.getFreq() != (uint32_t)raw[k].second)
        {
            cout << "  mismatch at posting " << k << endl;
            return false;
        }
    }
    return true;
}

void testTerm(const string &term, const map<string, LexEntry> &lexicon)
{
    cout << "Testing term: " << term << endl;
    vector<pair<int, int>> raw = getRaw(term);

    InvertedList list;
    bool opened = list.open(term, lexicon);

    if (raw.empty())
    {
        check(!opened, term + " should not open");
        return;
    }
    check(opened, term + " should open");
    if (!opened)
        return;

    // should start on the first posting
    check(list.getDF() == (int)raw.size(), term + " df");
    check(list.getDocID() == (uint32_t)raw[0].first, term + " first docID");
    check(list.getFreq() == (uint32_t)raw[0].second, term + " first freq");
    list.close();

    check(seekTest(term, lexicon, raw, 1), term + " every posting");
    check(seekTest(term, lexicon, raw, 37), term + " skipping ahead");

    // past the last posting
    list.open(term, lexicon);
    check(list.nextGEQ(raw.back().first + 1) == NOT_FOUND, term + " past the end");
    list.close();

    // smaller target shouldn't move us back
    list.open(term, lexicon);
    uint32_t mid = raw[raw.size() / 2].first;
    list.nextGEQ(mid);
    check(list.nextGEQ(0) == mid, term + " no going backwards");
    list.close();
}

int main(int argc, char **argv)
{
    map<string, LexEntry> lexicon = loadLexicon("lexicon.txt");

    vector<string> terms;
    for (int i = 1; i < argc; i++)
        terms.push_back(argv[i]);
    if (terms.empty())
        terms = {"the", "magic", "zzzznotaword"};

    for (const string &t : terms)
        testTerm(t, lexicon);

    cout << "\nPassed: " << passed << "  Failed: " << failed << endl;
    return 0;
}