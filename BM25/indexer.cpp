#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdint>
#include <map>
#include <cctype>
#include <algorithm>
#include <filesystem>
using namespace std;

const size_t memory_limit = 5000000; // limit for main memory
const int MAX_DOCS = 10000000;       // stop after this many docs (raised above 8.8 milli)
// tokenizer (from the parser)
vector<string> tokens(string text)
{
   vector<string> token_list;
   for (auto &c : text)
   {
      if (ispunct(static_cast<unsigned char>(c)) && c != '\'') // ignore apostrophe's here
         c = ' ';                                              // punctuation becomes a space, so words stay separate
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

void flushRun(map<string, vector<pair<int, int>>> &postings, int &runCount) // at the end, data is safe in disk so i can flush it out of RAM
{
   ofstream runFile("runs/run_" + to_string(runCount) + ".bin", ios::binary); // opens file and writes
   if (!runFile)
   {
      cerr << "Could not open runs/run_" << runCount << ".bin for writing" << endl;
      exit(1);
   }
   for (const auto &[term, docList] : postings)
   {
      runFile << term; // for example, "magic"
      for (const auto &[docID, freq] : docList)
         runFile << ' ' << docID << ' ' << freq; // loops through the docs and writes docid, freq
      runFile << '\n';
   }
   postings.clear(); // removes from RAM to make room for next run - current postings saved in run file
   runCount++;       // need this for later
   // "magic": apple [2 1] [15 3] [40 1]
}

int main(int argc, char **argv)
{
   filesystem::remove_all("runs");
   filesystem::create_directory("runs");
   ifstream file("collection.tsv"); // Opens the collection.tsv file for reading
   if (!file)
   {
      cerr << "Could not open collection.tsv" << endl;
      return 1;
   }
   ofstream mappingFile("docid_map.bin", ios::binary); // Writes to a binary file about the docIDs
   if (!mappingFile)
   {
      cerr << "Could not open docid_map.bin for writing" << endl;
      return 1;
   }
   ofstream docLengths("doc_length.bin", ios::binary); // binary file letting us know document length (uint32)
   map<string, vector<pair<int, int>>> postings;       // map of terms to a vector of pairs (docID, frequency) - note that the map automatically sorts by alphabetical order, which is imp for merger.cpp
   size_t postingCount = 0;
   int runCount = 0;
   int nextDocID = 0;
   string line;
   while (getline(file, line))
   {
      if (nextDocID >= MAX_DOCS)
         break;
      vector<string> parts;
      string field;
      istringstream ss(line);
      while (getline(ss, field, '\t'))
      { // splits the line into parts based on tabs because its a tsv file
         parts.push_back(field);
      }

      if (parts.empty())
         continue;
      int docID = nextDocID++;                          // counter to assign a unique docIDs
      string text = (parts.size() > 1) ? parts[1] : ""; // case where Id has no text :(

      uint64_t originID = stoull(parts[0]);                                           // need to convert from string
      mappingFile.write(reinterpret_cast<const char *>(&originID), sizeof(originID)); // mapping msMARCOID to docID, at position = docid
      vector<string> tokies = tokens(text);                                           // call token function to get the length and frequency
      uint32_t docLength = static_cast<uint32_t>(tokies.size());
      docLengths.write(reinterpret_cast<const char *>(&docLength), sizeof(docLength)); // number of terms in one doc
      if (nextDocID % 100000 == 0)
         cout << "Parsed " << nextDocID << " documents" << endl;
      map<string, int> termFreq; // how many times did a term appear ie. "magic" appeared 2 times
      for (const auto &token : tokies)
      {
         termFreq[token]++;
      }
      for (const auto &[term, freq] : termFreq)
      {
         postings[term].push_back({docID, freq}); // build postings ie. [magic] {2,15}
         postingCount++;                          // how many postings in this run file OR tell indexer RAM is full
      }
      if (postingCount >= memory_limit)
      {
         flushRun(postings, runCount); // bye flushed out of RAM
         postingCount = 0;
      }
   }
   if (!postings.empty())
   {
      flushRun(postings, runCount);
   }
   mappingFile.close();
   docLengths.close();
   ofstream count_file("runs/run_count.txt");
   count_file << runCount; // need to keep tarack of number of runfiles - every time we collect 5 million postings we call flushrun
   count_file.close();
   cout << "Done, parsed " << nextDocID << " documents, " << runCount << " runs" << endl;
   return 0;
}
