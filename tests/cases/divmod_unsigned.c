// EXPECT: 0
// Unsigned 16-bit / and % (libgcc1.s _udivhi3/_umodhi3 over _euclid).
// Covers operands with bit 15 set on either side, 65535 as dividend and
// divisor, dividend < divisor, and quotients that need all 16 bits.
// Expected values were computed on the host (Python), not with this
// toolchain.  Returns 0, or the 1-based index of the first table entry
// whose quotient or remainder is wrong.  Division by zero is undefined in
// C and is checked at the helper level by tests/review/run_divmod_review.py.

static const struct { unsigned int a, b, q, r; } cases[] = {
    { 65535u, 1, 65535u, 0 }, { 65535u, 65535u, 1, 0 },
    { 65535u, 2, 32767u, 1 }, { 65535u, 3, 21845u, 0 },
    { 65535u, 256, 255, 255 }, { 65535u, 255, 257, 0 }, { 65535u, 257, 255, 0 },
    { 65535u, 32767u, 2, 1 }, { 65535u, 32768u, 1, 32767u },
    { 65534u, 32767u, 2, 0 }, { 32768u, 32768u, 1, 0 }, { 32767u, 32768u, 0, 32767u },
    { 32768u, 1, 32768u, 0 }, { 32768u, 2, 16384u, 0 }, { 32768u, 3, 10922u, 2 },
    { 32768u, 7, 4681u, 1 }, { 32768u, 65535u, 0, 32768u }, { 32769u, 32768u, 1, 1 },
    { 1, 65535u, 0, 1 }, { 0, 65535u, 0, 0 }, { 0, 1, 0, 0 },
    { 40000u, 3, 13333u, 1 }, { 60000u, 7, 8571u, 3 }, { 50000u, 50000u, 1, 0 },
    { 49999u, 50000u, 0, 49999u }, { 65535u, 65534u, 1, 1 },
    { 65280u, 256, 255, 0 }, { 65281u, 256, 255, 1 }, { 12345u, 100, 123, 45 },
    { 7, 2, 3, 1 }, { 42, 6, 7, 0 }, { 255, 256, 0, 255 }, { 256, 255, 1, 1 },
    { 65535u, 10, 6553u, 5 }, { 65535u, 100, 655u, 35 },
    { 65535u, 4096u, 15, 4095u }, { 61440u, 4096u, 15, 0 },
};

int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        volatile unsigned int a = cases[i].a;
        volatile unsigned int b = cases[i].b;
        if (a / b != cases[i].q || a % b != cases[i].r)
            return (int)i + 1;
    }
    return 0;
}
