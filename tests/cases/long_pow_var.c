// EXPECT: 3
// Integer power with long base and exponent by repeated multiplication, the
// shape of luai_ipow in lua-6809, which returned 0 for 2^10 with the swapped
// push order (bug 1).
__attribute__((noinline)) long ipow(long b, long e)
{
    long r = 1;
    while (e > 0) {
        if (e & 1) r *= b;
        b *= b;
        e >>= 1;
    }
    return r;
}

volatile long vb = 2, ve = 10;

int main(void)
{
    int r = 0;
    if (ipow(vb, ve) == 1024L) r |= 1;
    if (ipow(4L, 8L) == 65536L) r |= 2;
    return r;
}
