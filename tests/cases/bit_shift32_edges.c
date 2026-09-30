// EXPECT: 0
// Defined unsigned shifts and this target's arithmetic signed right shift.
// Every count is strictly less than the operand width; no signed left shift.
// Golden results are constants, not calculations through the same helpers.
#define NOINLINE __attribute__((noinline))
NOINLINE unsigned long left(unsigned long x, int n) { return x << n; }
NOINLINE unsigned long logical(unsigned long x, int n) { return x >> n; }
NOINLINE long arithmetic(long x, int n) { return x >> n; }
struct vector {
    unsigned long value;
    long signed_value;
    int count;
    unsigned long left, logical, arithmetic;
};
static const struct vector vectors[] = {
    {0x00000000UL, 0L, 0, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 1, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 7, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 8, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 15, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 16, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 17, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 23, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 24, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 30, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000000UL, 0L, 31, 0x00000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 0, 0x00000001UL, 0x00000001UL, 0x00000001UL},
    {0x00000001UL, 1L, 1, 0x00000002UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 7, 0x00000080UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 8, 0x00000100UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 15, 0x00008000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 16, 0x00010000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 17, 0x00020000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 23, 0x00800000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 24, 0x01000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 30, 0x40000000UL, 0x00000000UL, 0x00000000UL},
    {0x00000001UL, 1L, 31, 0x80000000UL, 0x00000000UL, 0x00000000UL},
    {0x7fffffffUL, 2147483647L, 0, 0x7fffffffUL, 0x7fffffffUL, 0x7fffffffUL},
    {0x7fffffffUL, 2147483647L, 1, 0xfffffffeUL, 0x3fffffffUL, 0x3fffffffUL},
    {0x7fffffffUL, 2147483647L, 7, 0xffffff80UL, 0x00ffffffUL, 0x00ffffffUL},
    {0x7fffffffUL, 2147483647L, 8, 0xffffff00UL, 0x007fffffUL, 0x007fffffUL},
    {0x7fffffffUL, 2147483647L, 15, 0xffff8000UL, 0x0000ffffUL, 0x0000ffffUL},
    {0x7fffffffUL, 2147483647L, 16, 0xffff0000UL, 0x00007fffUL, 0x00007fffUL},
    {0x7fffffffUL, 2147483647L, 17, 0xfffe0000UL, 0x00003fffUL, 0x00003fffUL},
    {0x7fffffffUL, 2147483647L, 23, 0xff800000UL, 0x000000ffUL, 0x000000ffUL},
    {0x7fffffffUL, 2147483647L, 24, 0xff000000UL, 0x0000007fUL, 0x0000007fUL},
    {0x7fffffffUL, 2147483647L, 30, 0xc0000000UL, 0x00000001UL, 0x00000001UL},
    {0x7fffffffUL, 2147483647L, 31, 0x80000000UL, 0x00000000UL, 0x00000000UL},
    {0x80000000UL, (-2147483647L - 1), 0, 0x80000000UL, 0x80000000UL, 0x80000000UL},
    {0x80000000UL, (-2147483647L - 1), 1, 0x00000000UL, 0x40000000UL, 0xc0000000UL},
    {0x80000000UL, (-2147483647L - 1), 7, 0x00000000UL, 0x01000000UL, 0xff000000UL},
    {0x80000000UL, (-2147483647L - 1), 8, 0x00000000UL, 0x00800000UL, 0xff800000UL},
    {0x80000000UL, (-2147483647L - 1), 15, 0x00000000UL, 0x00010000UL, 0xffff0000UL},
    {0x80000000UL, (-2147483647L - 1), 16, 0x00000000UL, 0x00008000UL, 0xffff8000UL},
    {0x80000000UL, (-2147483647L - 1), 17, 0x00000000UL, 0x00004000UL, 0xffffc000UL},
    {0x80000000UL, (-2147483647L - 1), 23, 0x00000000UL, 0x00000100UL, 0xffffff00UL},
    {0x80000000UL, (-2147483647L - 1), 24, 0x00000000UL, 0x00000080UL, 0xffffff80UL},
    {0x80000000UL, (-2147483647L - 1), 30, 0x00000000UL, 0x00000002UL, 0xfffffffeUL},
    {0x80000000UL, (-2147483647L - 1), 31, 0x00000000UL, 0x00000001UL, 0xffffffffUL},
    {0x80000001UL, -2147483647L, 0, 0x80000001UL, 0x80000001UL, 0x80000001UL},
    {0x80000001UL, -2147483647L, 1, 0x00000002UL, 0x40000000UL, 0xc0000000UL},
    {0x80000001UL, -2147483647L, 7, 0x00000080UL, 0x01000000UL, 0xff000000UL},
    {0x80000001UL, -2147483647L, 8, 0x00000100UL, 0x00800000UL, 0xff800000UL},
    {0x80000001UL, -2147483647L, 15, 0x00008000UL, 0x00010000UL, 0xffff0000UL},
    {0x80000001UL, -2147483647L, 16, 0x00010000UL, 0x00008000UL, 0xffff8000UL},
    {0x80000001UL, -2147483647L, 17, 0x00020000UL, 0x00004000UL, 0xffffc000UL},
    {0x80000001UL, -2147483647L, 23, 0x00800000UL, 0x00000100UL, 0xffffff00UL},
    {0x80000001UL, -2147483647L, 24, 0x01000000UL, 0x00000080UL, 0xffffff80UL},
    {0x80000001UL, -2147483647L, 30, 0x40000000UL, 0x00000002UL, 0xfffffffeUL},
    {0x80000001UL, -2147483647L, 31, 0x80000000UL, 0x00000001UL, 0xffffffffUL},
    {0x89abcdefUL, -1985229329L, 0, 0x89abcdefUL, 0x89abcdefUL, 0x89abcdefUL},
    {0x89abcdefUL, -1985229329L, 1, 0x13579bdeUL, 0x44d5e6f7UL, 0xc4d5e6f7UL},
    {0x89abcdefUL, -1985229329L, 7, 0xd5e6f780UL, 0x0113579bUL, 0xff13579bUL},
    {0x89abcdefUL, -1985229329L, 8, 0xabcdef00UL, 0x0089abcdUL, 0xff89abcdUL},
    {0x89abcdefUL, -1985229329L, 15, 0xe6f78000UL, 0x00011357UL, 0xffff1357UL},
    {0x89abcdefUL, -1985229329L, 16, 0xcdef0000UL, 0x000089abUL, 0xffff89abUL},
    {0x89abcdefUL, -1985229329L, 17, 0x9bde0000UL, 0x000044d5UL, 0xffffc4d5UL},
    {0x89abcdefUL, -1985229329L, 23, 0xf7800000UL, 0x00000113UL, 0xffffff13UL},
    {0x89abcdefUL, -1985229329L, 24, 0xef000000UL, 0x00000089UL, 0xffffff89UL},
    {0x89abcdefUL, -1985229329L, 30, 0xc0000000UL, 0x00000002UL, 0xfffffffeUL},
    {0x89abcdefUL, -1985229329L, 31, 0x80000000UL, 0x00000001UL, 0xffffffffUL},
    {0xffffffffUL, -1L, 0, 0xffffffffUL, 0xffffffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 1, 0xfffffffeUL, 0x7fffffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 7, 0xffffff80UL, 0x01ffffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 8, 0xffffff00UL, 0x00ffffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 15, 0xffff8000UL, 0x0001ffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 16, 0xffff0000UL, 0x0000ffffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 17, 0xfffe0000UL, 0x00007fffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 23, 0xff800000UL, 0x000001ffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 24, 0xff000000UL, 0x000000ffUL, 0xffffffffUL},
    {0xffffffffUL, -1L, 30, 0xc0000000UL, 0x00000003UL, 0xffffffffUL},
    {0xffffffffUL, -1L, 31, 0x80000000UL, 0x00000001UL, 0xffffffffUL},
};
volatile int runtime_count;
int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        runtime_count = vectors[i].count;
        if (left(vectors[i].value, runtime_count) != vectors[i].left)
            return 100 + i;
        if (logical(vectors[i].value, runtime_count) != vectors[i].logical)
            return 200 + i;
        if ((unsigned long)arithmetic(vectors[i].signed_value, runtime_count) != vectors[i].arithmetic)
            return 300 + i;
    }
    return 0;
}
