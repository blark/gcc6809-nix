// EXPECT: 42
// Test struct pointer access
struct point {
    int x;
    int y;
};

int main(void) {
    struct point p;
    struct point *pp = &p;
    pp->x = 20;
    pp->y = 22;
    return pp->x + pp->y;
}
