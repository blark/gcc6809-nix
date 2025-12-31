// EXPECT: 42
// Test unsigned int
int main(void) {
    unsigned int a = 40000;
    unsigned int b = 25536;
    unsigned int diff = a - b;  // 14464
    return diff / 344;  // 14464 / 344 = 42
}
