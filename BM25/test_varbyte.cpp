#include <iostream>
#include <vector>
#include <cstdint>
using namespace std;

void varbyteEncode(uint32_t n, vector<uint8_t> &out)
{
    while (n >= 128)
    {
        out.push_back(static_cast<uint8_t>((n & 127) | 128));
        n >>= 7;
    }
    out.push_back(static_cast<uint8_t>(n));
}

uint32_t varbyteDecode(const vector<uint8_t> &data, size_t &pos)
{
    uint32_t n = 0;
    int shift = 0;
    while (true)
    {
        uint8_t b = data[pos++];
        n |= static_cast<uint32_t>(b & 127) << shift;
        if (!(b & 128))
            break;
        shift += 7;
    }
    return n;
}

int main()
{
    uint32_t tests[] = {0, 1, 127, 128, 300, 16384, 4000000000u};
    for (uint32_t t : tests)
    {
        vector<uint8_t> buf;
        varbyteEncode(t, buf);
        size_t pos = 0;
        uint32_t back = varbyteDecode(buf, pos);
        cout << t << " -> " << buf.size() << " byte(s) -> " << back
             << (back == t ? "  OK" : "  MISMATCH") << endl;
    }
}