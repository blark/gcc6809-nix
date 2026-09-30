// EXPECT: 36
// Regression test: 32-bit div/mod in a loop used to crash the compiler
// ("unrecognizable insn" with a pre_dec push of a 32-bit constant, fixed by
// movsi-fix.patch).  1+2+3+4+5+6+7+8 = 36.
int main(void) {
    long n = 12345678L;
    int sum = 0;

    while (n > 0) {
        sum += (int)(n % 10);
        n = n / 10;
    }

    return sum;
}
