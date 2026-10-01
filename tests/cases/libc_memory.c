// EXPECT: 0
// ISO C byte-copy/set/compare contracts; memmove alone receives overlap.
#include <string.h>

volatile size_t count = 12;
static unsigned char buf[24];
static unsigned char source[24];

int main(void)
{
    unsigned int i;
    void *p;
    for (i = 0; i < 24; ++i) {
        source[i] = (unsigned char)(i * 9 + 3);
        buf[i] = 0xa5;
    }
    p = memcpy(buf + 2, source + 4, count);
    if (p != buf + 2) return 1;
    for (i = 0; i < 24; ++i)
        if (buf[i] != (i >= 2 && i < 14 ? source[i + 2] : 0xa5)) return 2;
    if (memcmp(buf + 2, source + 4, count) != 0) return 3;
    if (memcmp(buf + 2, source + 5, 1) >= 0) return 4;
    if (memcmp(source + 5, source + 4, 1) <= 0) return 5;
    if (memcmp(source, source + 1, 0) != 0) return 6;

    for (i = 0; i < 24; ++i) buf[i] = (unsigned char)i;
    p = memmove(buf + 3, buf, count); // destination starts inside source
    if (p != buf + 3) return 7;
    for (i = 0; i < 24; ++i)
        if (buf[i] != (i >= 3 && i < 15 ? i - 3 : i)) return 8;

    for (i = 0; i < 24; ++i) buf[i] = (unsigned char)i;
    p = memmove(buf, buf + 3, count); // source starts inside destination
    if (p != buf) return 9;
    for (i = 0; i < 24; ++i)
        if (buf[i] != (i < 12 ? i + 3 : i)) return 10;

    p = memset(buf + 5, 0x1a5, count); // low unsigned-char bits: 0xa5
    if (p != buf + 5) return 11;
    for (i = 0; i < 24; ++i)
        if (buf[i] != (i >= 5 && i < 17 ? 0xa5 : (i < 12 ? i + 3 : i)))
            return 12;
    return 0;
}
