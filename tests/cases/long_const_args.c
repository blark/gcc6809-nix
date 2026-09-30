// EXPECT: 15
// 32-bit constants pushed as arguments and stored to memory, of every shape
// that used to make the compiler crash: a half >= 0x8000, -1L, 40000UL and
// 0x12345678 (bug 2: unrecognizable insn / ICE in extract_insn).
#define NOINLINE __attribute__((noinline))

NOINLINE long add2(long a, long b) { return a + b; }
NOINLINE int check(long a, unsigned long b, long c, long d)
{
    return (a == -1L) + (b == 40000UL) * 2 + (c == 0x12345678L) * 4
         + (d == (long)0x80008000L) * 8;
}

long g1, g4;
unsigned long g2;
long g3;

int main(void)
{
    int r = 0;
    g1 = -1L;
    g2 = 40000UL;
    g3 = 0x12345678L;
    g4 = (long)0x80008000L;
    if (check(g1, g2, g3, g4) == 15) r |= 1;
    if (check(-1L, 40000UL, 0x12345678L, (long)0x80008000L) == 15) r |= 2;
    if (add2(0x12345678L, 0x00010002L) == 0x1235567AL) r |= 4;
    if (add2(-1L, 1L) == 0L && add2(0x7FFFFFFFL, 1L) == (long)0x80000000L) r |= 8;
    return r;
}
