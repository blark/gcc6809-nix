// EXPECT: 15
// Sum 1+2+3+4+5
int main(void) {
    int sum = 0;
    for (int i = 1; i <= 5; i++) {
        sum += i;
    }
    return sum;
}
