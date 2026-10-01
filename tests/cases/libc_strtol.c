// EXPECT: 0
// strtol: valid bases, whitespace/sign, end pointer and no-conversion cases.
// Inputs stay within 32-bit long range; no errno or overflow assumptions.
#include <stdlib.h>

static char input[40];
volatile int base;
static void copy(const char *source)
{
    unsigned int i;
    for (i = 0; (input[i] = source[i]) != 0; ++i) { }
}

int main(void)
{
    char *end;
    long got;
    copy("  -12345xyz");
    base = 10;
    got = strtol(input, &end, base);
    if (got != -12345L || end != input + 8 || *end != 'x') return 1;
    copy("0x7fffffff!");
    base = 0;
    got = strtol(input, &end, base);
    if (got != 2147483647L || end != input + 10 || *end != '!') return 2;
    copy("-2147483648;");
    base = 10;
    got = strtol(input, &end, base);
    if (got != (-2147483647L - 1) || end != input + 11) return 3;
    copy("0759");
    base = 0;
    got = strtol(input, &end, base);
    if (got != 61L || end != input + 3 || *end != '9') return 4;
    copy("z!");
    base = 36;
    got = strtol(input, &end, base);
    if (got != 35L || end != input + 1) return 5;
    copy("-x");
    base = 10;
    got = strtol(input, &end, base);
    if (got != 0 || end != input) return 6;
    copy("   +");
    got = strtol(input, &end, base);
    if (got != 0 || end != input) return 7;
    copy("0x");
    base = 16;
    got = strtol(input, &end, base);
    if (got != 0 || end != input) return 8; // newlib 1.15: prefix without digits
    copy("10");
    base = 2;
    got = strtol(input, &end, base);
    if (got != 2 || end != input + 2) return 9;
    return 0;
}
