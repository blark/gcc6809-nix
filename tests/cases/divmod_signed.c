// EXPECT: 0
// Signed 16-bit / and % (libgcc1.s _divhi3/_modhi3 over _seuclid).
// C99 6.5.5: the quotient truncates toward zero and (a/b)*b + a%b == a, so
// the remainder takes the dividend's sign.  Covers all four sign
// combinations, INT_MIN as dividend and divisor, and both bytes of the
// operands.  Expected values were computed on the host (Python), not with
// this toolchain.  Returns 0, or the 1-based index of the first table entry
// whose quotient or remainder is wrong.
// INT_MIN / -1 and division by zero are undefined in C, so they are checked
// at the helper level by tests/review/run_divmod_review.py instead.
#define INT_MIN_ (-32767 - 1)

static const struct { int a, b, q, r; } cases[] = {
    { 7, 2, 3, 1 }, { -7, 2, -3, -1 }, { 7, -2, -3, 1 }, { -7, -2, 3, -1 },
    { 1, 3, 0, 1 }, { -1, 3, 0, -1 }, { 1, -3, 0, 1 }, { -1, -3, 0, -1 },
    { 0, 5, 0, 0 }, { 0, -5, 0, 0 },
    { 42, 6, 7, 0 }, { -42, 6, -7, 0 }, { 42, -6, -7, 0 }, { -42, -6, 7, 0 },
    { 32767, 1, 32767, 0 }, { 32767, -1, -32767, 0 }, { -32767, -1, 32767, 0 },
    { 32767, 2, 16383, 1 }, { 32767, 32767, 1, 0 }, { 32767, -32767, -1, 0 },
    { INT_MIN_, 1, INT_MIN_, 0 }, { INT_MIN_, 2, -16384, 0 },
    { INT_MIN_, -2, 16384, 0 },
    { INT_MIN_, 3, -10922, -2 }, { INT_MIN_, -3, 10922, -2 },
    { INT_MIN_, 7, -4681, -1 }, { INT_MIN_, 32767, -1, -1 },
    { INT_MIN_, -32767, 1, -1 },
    { INT_MIN_, INT_MIN_, 1, 0 },
    { 1, INT_MIN_, 0, 1 }, { -1, INT_MIN_, 0, -1 },
    { 32767, INT_MIN_, 0, 32767 }, { -32767, INT_MIN_, 0, -32767 },
    { 255, 256, 0, 255 }, { 256, 255, 1, 1 }, { -256, 255, -1, -1 },
    { 257, -256, -1, 1 },
    { 12345, 100, 123, 45 }, { -12345, 100, -123, -45 },
    { 12345, -100, -123, 45 },
    { 30000, 10000, 3, 0 }, { -30000, 10000, -3, 0 }, { 10000, 30000, 0, 10000 },
    { 0x7F00, 0x0100, 127, 0 }, { -0x7F00, 0x0100, -127, 0 },
};

int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        volatile int a = cases[i].a;
        volatile int b = cases[i].b;
        if (a / b != cases[i].q || a % b != cases[i].r)
            return (int)i + 1;
    }
    return 0;
}
