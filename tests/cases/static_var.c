// EXPECT: 42
// Test static variable
int increment(void) {
    static int counter = 0;
    counter += 7;
    return counter;
}

int main(void) {
    increment();  // 7
    increment();  // 14
    increment();  // 21
    increment();  // 28
    increment();  // 35
    return increment();  // 42
}
