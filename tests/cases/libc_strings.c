// EXPECT: 0
// strcmp/strncmp signs and NUL handling; no assumptions about magnitude.
#include <string.h>

static char left[40];
static char right[40];
volatile unsigned int bound;

int main(void)
{
    unsigned int i;
    for (i = 0; i < 39; ++i) {
        left[i] = 'a';
        right[i] = 'a';
    }
    left[39] = right[39] = 0;
    if (strlen(left) != 39 || strcmp(left, right) != 0) return 1;
    bound = 38;
    right[38] = 'b';
    if (strncmp(left, right, bound) != 0) return 2;
    bound = 39;
    if (strncmp(left, right, bound) >= 0) return 3;
    if (strcmp(right, left) <= 0) return 4;
    right[38] = 'a';
    left[12] = 0;
    if (strlen(left) != 12 || strcmp(left, right) >= 0) return 5;
    if (strncmp(left, right, 12) != 0 || strncmp(left, right, 13) >= 0) return 6;
    if (strncmp(left, right, 0) != 0) return 7;
    if (strchr(left, 'a') != left || strchr(left, 0) != left + 12) return 8;
    if (strchr(left, 'z') != 0) return 9;
    left[0] = (char)0x80;
    right[0] = 0x7f;
    if (strcmp(left, right) <= 0) return 10; // compare bytes as unsigned char
    return 0;
}
