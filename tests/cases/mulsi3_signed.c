// EXPECT: 0
// Signed 32-bit multiply through the same helper (___mulsi3 serves long
// and unsigned long).  Every product here fits in a long, so the C result
// is defined; the operands are negative or straddle LONG_MIN so the helper
// sees two's-complement bit patterns with high bits set and its partial
// products carry across all four bytes.  Operands are long literals: no
// int-to-long conversion of a negative value is involved, so the 6809 SEX
// instruction (mis-emulated by MC6809 0.6.0, see gcc6809-877) is not on
// the path.  Expected values from Python.  Returns 0, or the 1-based index
// of the first wrong product.

static const struct { long a, b, p; } cases[] = {
    { -1L, -1L, 1L },
    { -1L, 1L, -1L },
    { 1L, -1L, -1L },
    { (-2147483647L - 1), 1L, (-2147483647L - 1) },
    { 1L, (-2147483647L - 1), (-2147483647L - 1) },
    { -2147483647L, -1L, 2147483647L },
    { -1L, 2147483647L, -2147483647L },
    { -3L, 5L, -15L },
    { 5L, -3L, -15L },
    { -3L, -5L, 15L },
    { -65536L, 32768L, (-2147483647L - 1) },
    { 65536L, -32767L, -2147418112L },
    { -65535L, 32767L, -2147385345L },
    { -46341L, 46340L, -2147441940L },
    { 46340L, -46341L, -2147441940L },
    { -46340L, -46340L, 2147395600L },
    { -1L, 0L, 0L },
    { 0L, -1L, 0L },
    { (-2147483647L - 1), 0L, 0L },
    { -123456789L, 17L, -2098765413L },
    { 17L, -123456789L, -2098765413L },
    { -1000000L, 2147L, -2147000000L },
    { -99991L, -21474L, 2147206734L },
    { -4096L, -524287L, 2147479552L },
    { -32768L, 65536L, (-2147483647L - 1) },
    { 32768L, -65536L, (-2147483647L - 1) },
};

int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        volatile long a = cases[i].a;
        volatile long b = cases[i].b;
        if (a * b != cases[i].p)
            return (int)i + 1;
    }
    return 0;
}
