// EXPECT: 42
// Test indirect function call through stack variable
int add(int a, int b) {
    return a + b;
}

int call_via_ptr(int (*fp)(int, int), int x, int y) {
    return fp(x, y);
}

int main(void) {
    return call_via_ptr(add, 20, 22);
}
