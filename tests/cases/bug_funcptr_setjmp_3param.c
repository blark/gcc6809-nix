// EXPECT: 42
// Regression test: indirect call through a function-pointer parameter after
// setjmp, with 3+ params and struct pointer dereferences before the setjmp.
// The pointer is spilled to the stack, and the call used a stale [n,s]
// offset once the arguments were pushed (indirect-call-stack-offset.patch).
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
