// EXPECT: 0
// XFAIL: mulqihi3 in m6809.md multiplies sign-extended chars with the unsigned MUL instruction
// signed char * signed char with a negative operand.  At -Os and -O2 GCC
// matches the mulqihi3 pattern, "lda %2; mul", but MUL is unsigned, so
// (-1) * (-1) yields 255 * 255 = 0xFE01 instead of 1.  At -O0 the operands
// are sign-extended with SEX and _mulhi3 is called, which is correct code;
// it still fails on the MC6809 0.6.0 emulator because its SEX does not
// set A for a negative B (gcc6809-877).  Returns 0, or the number of the
// first failing check.

#define NOINLINE __attribute__((noinline))

NOINLINE int mulqi(signed char a, signed char b) { return a * b; }
NOINLINE int mulqi_const(signed char a) { return a * 3; }

int main(void)
{
    if (mulqi(-1, -1) != 1) return 1;
    if (mulqi(-2, 3) != -6) return 2;
    if (mulqi_const(-1) != -3) return 3;
    if (mulqi(100, 100) != 10000) return 4;
    if (mulqi(-128, -128) != 16384) return 5;
    return 0;
}
