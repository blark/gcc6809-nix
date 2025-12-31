// EXPECT: 42
// Test nested function calls
int add(int a, int b) { return a + b; }
int mul(int a, int b) { return a * b; }

int main(void) {
    return add(mul(3, 4), mul(5, 6));  // 12 + 30 = 42
}
