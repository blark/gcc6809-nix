// EXPECT: 42
// Test 32-bit multiplication with variables (not constants)
long a = 6;
long b = 7;

int main(void) {
    long result = a * b;
    return (int)result;
}
