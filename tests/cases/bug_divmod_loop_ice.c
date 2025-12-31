// EXPECT: 21
// XFAIL: ICE with 32-bit div/mod in loop (pre_dec addressing mode bug)
// BUG: gcc6809 ICE when compiling 32-bit div/mod in a loop
// Compiler crashes with "internal compiler error: in extract_insn"
// This test will fail to compile, not fail at runtime.
int main(void) {
    long n = 12345678L;
    int sum = 0;

    while (n > 0) {
        sum += (int)(n % 10);
        n = n / 10;
    }

    // 1+2+3+4+5+6+7+8 = 36, but compiler crashes before we get there
    return sum;
}
