// EXPECT: 4
// Test 32-bit shift
long x = 256;

int main(void) {
    long y = x >> 6;  // 256 >> 6 = 4
    return (int)y;
}
