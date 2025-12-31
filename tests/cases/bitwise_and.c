// EXPECT: 42
int main(void) {
    int a = 0xFF;
    int b = 0x2A;  // 42
    return a & b;
}
