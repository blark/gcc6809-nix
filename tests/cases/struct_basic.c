// EXPECT: 42
// Test basic struct
struct point {
    int x;
    int y;
};

int main(void) {
    struct point p;
    p.x = 20;
    p.y = 22;
    return p.x + p.y;
}
