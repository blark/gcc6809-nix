// EXPECT: 1
// A broken longjmp returns through case 0 twice; the guard prevents a loop.
#include <setjmp.h>

static jmp_buf env;
static volatile int jumped;

int main(void)
{
    switch (setjmp(env)) {
    case 0:
        if (jumped)
            return 0;
        jumped = 1;
        longjmp(env, 0);
        return 2;
    case 1:
        return jumped == 1;
    default:
        return 3;
    }
}
