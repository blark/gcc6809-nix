// EXPECT: 42
// Test function with multiple arguments
int sum5(int a, int b, int c, int d, int e) {
    return a + b + c + d + e;
}

int main(void) {
    return sum5(1, 2, 4, 15, 20);
}
