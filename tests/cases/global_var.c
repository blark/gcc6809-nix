// EXPECT: 42
// Test global variable
int global = 20;

int main(void) {
    global = global + 22;
    return global;
}
