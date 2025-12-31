// EXPECT: 42
// XFAIL: indirect call after setjmp jumps to wrong address
// BUG: gcc6809 generates wrong code for indirect call after setjmp
// Conditions: 3+ params, struct pointer dereferences before setjmp,
// then indirect call through function pointer parameter.
// Workaround: copy f and ud to volatile locals before setjmp.
// Crashes with "UNKNOWN OP" - jumps to wrong address.
#include <setjmp.h>

typedef void (*Pfunc)(void*, void*);

struct lua_longjmp {
    struct lua_longjmp *previous;
    jmp_buf b;
    volatile int status;
};

struct State {
    struct lua_longjmp *errorJmp;
};

static int test_result;

void test_func(void* L, void* ud) {
    (void)L;
    test_result = (int)(long)ud;
}

int rawrunprotected(struct State *L, Pfunc f, void *ud) {
    struct lua_longjmp lj;
    lj.status = 0;
    lj.previous = L->errorJmp;
    L->errorJmp = &lj;
    if (setjmp(lj.b) == 0) {
        (*f)(L, ud);  // indirect call after setjmp
    }
    L->errorJmp = lj.previous;
    return lj.status;
}

int main(void) {
    struct State state;
    state.errorJmp = 0;
    test_result = 0;
    rawrunprotected(&state, test_func, (void*)42);
    return test_result;
}
