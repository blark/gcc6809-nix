// EXPECT: 1
// Exercise both bytes of val, signed boundaries, and repeated reuse of env.
#include <setjmp.h>

static jmp_buf env;
static volatile int value;
static volatile int jumped;
static const int values[] = { 0, 1, 2, 255, 256, 257, 32767, -1, -256, -32767 - 1 };

__attribute__((noinline)) static int check(void)
{
    jumped = 0;
    switch (setjmp(env)) {
    case 0:
        if (jumped)
            return 0;
        jumped = 1;
        longjmp(env, value);
        return 0;
    case 1:      return jumped && (value == 0 || value == 1);
    case 2:      return jumped && value == 2;
    case 255:    return jumped && value == 255;
    case 256:    return jumped && value == 256;
    case 257:    return jumped && value == 257;
    case 32767:  return jumped && value == 32767;
    case -1:     return jumped && value == -1;
    case -256:   return jumped && value == -256;
    case (-32767 - 1): return jumped && value == (-32767 - 1);
    default:     return 0;
    }
}

int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(values) / sizeof(values[0]); ++i) {
        value = values[i];
        if (!check())
            return 0;
    }
    return 1;
}
