# Bug: 32-bit multiplication returns 0

## Summary
`___mulsi3` from libgcc2.c doesn't write the result to the hidden result pointer passed in X register. The function computes the correct result internally but fails to store it to the memory location expected by the caller.

## Test Case
```c
// EXPECT: 42
long a = 6;
long b = 7;
int main(void) {
    long result = a * b;
    return (int)result;
}
```
Returns 0 instead of 42.

## Root Cause Analysis

### m6809 ABI for returning large values
For values larger than 16 bits (like `long` which is 32-bit), the m6809 ABI uses a hidden result pointer:
1. Caller allocates space for the result on the stack
2. Caller passes pointer to result area in X register
3. Callee writes result to *X before returning
4. Caller reads result from the pre-allocated area

### The Calling Side Works Correctly
When GCC compiles normal C code, it correctly:
- Allocates stack space for 32-bit results
- Passes the result pointer in X
- Reads the result from the allocated area after the call

Tested with simple functions - they correctly write to `,x` and `2,x`:
```asm
_simple_return:
    ...
    std  2,x    ; Store low word at X+2
    std  ,x     ; Store high word at X+0
    puls u,pc
```

### Evidence: Functions compiled by m6809-gcc work correctly

When compiling a simple function:
```c
long test_return_long(long a, long b) {
    return a + b;
}
```

The generated assembly correctly writes to X:
```asm
    std  2,x    ; Store low word at X+2
    std  ,x     ; Store high word at X+0
```

### Evidence: `___divsi3` from divmod.c works

`___divsi3` is compiled from `$GCC6809_SRC/gcc/config/divmod.c` (in LIB2FUNCS_EXTRA).
Trace shows result IS written to result area:
```
Return from ___divsi3:
   S+10: $0002  <-- correct result (6/3=2)
```

### Evidence: `___mulsi3` from libgcc2.c fails

`___mulsi3` comes from `$GCC6809_SRC/gcc/libgcc2.c` compiled with `-DL_muldi3`.
Trace shows result area is NOT written:
```
=== ENTERING ___mulsi3 ===
Result pointer: X=$FFEA
PC=$2025: STX 4,s - saving result ptr $FFEA at stack $FFC0
...
PC=$210D: PULS ...,PC - returning from ___mulsi3
Result area after: [FFEA]=$0000, [FFEC]=$0000   <-- NOT WRITTEN!
```

The function saves the result pointer but NEVER loads it back and NEVER writes to it.

## Key Difference: How the Functions Are Compiled

| Function | Source File | Build Method | Works? |
|----------|-------------|--------------|--------|
| `___divsi3` | `gcc/config/divmod.c` | LIB2FUNCS_EXTRA (compiled as separate C file) | YES |
| `___modsi3` | `gcc/config/divmod.c` | LIB2FUNCS_EXTRA | YES |
| `___mulsi3` | `gcc/libgcc2.c` | Internal libgcc2 build with -DL_muldi3 | NO |
| `_mulhi3` | `gcc/config/m6809/libgcc1.s` | LIB1ASMFUNCS (hand-written assembly) | YES |

The `libgcc2.c` file is compiled through GCC's internal build process with special headers:
```c
#include "tconfig.h"
#include "tsystem.h"
#include "coretypes.h"
#include "tm.h"
```

These headers are generated during GCC's configure/build and may have different settings than what the installed cross-compiler uses.

## Function Location Reference

### In libgcc1.s (assembly, LIB1ASMFUNCS):
- `_mulhi3` - 16x16->16 signed multiply
- `_divhi3`, `_modhi3` - 16-bit division/modulo
- `_udivhi3`, `_umodhi3` - unsigned 16-bit division/modulo
- `_ashlhi3`, `_ashrhi3`, `_lshrhi3` - 16-bit shifts
- Various other helpers

### In LIB2FUNCS_EXTRA (C source compiled correctly):
- `$GCC6809_SRC/gcc/config/udivmodsi4.c` - 32-bit unsigned divmod
- `$GCC6809_SRC/gcc/config/udivmod.c` - 32-bit unsigned div/mod wrappers
- `$GCC6809_SRC/gcc/config/divmod.c` - `__divsi3`, `__modsi3`

### In libgcc2.c (BROKEN via internal build):
- `___mulsi3` (from `__muldi3` renamed via `__NDW` macro)
- `___negsi2`, `___lshrsi3`, `___ashlsi3`, `___ashrsi3`, etc.

### Name Renaming in libgcc2.h
For 16-bit targets (LIBGCC2_UNITS_PER_WORD == 2):
```c
#define Wtype   HItype     // 16-bit word
#define DWtype  SItype     // 32-bit double-word
#define __NW(a,b)   __ ## a ## hi ## b   // word-sized -> hi
#define __NDW(a,b)  __ ## a ## si ## b   // double-word -> si
#define __muldi3    __NDW(mul,3)         // becomes __mulsi3
```

## Why the Internal Build Fails

The m6809 backend's `m6809_function_value()` returns:
```c
return gen_rtx_REG (mode, HARD_X_REGNUM);
```

For SImode (32-bit), this says "return value in X register" - but X is only 16 bits!

GCC normally detects this mismatch and uses struct-style return with a hidden pointer. However, during the internal libgcc2 build:
1. Different headers (tconfig.h, tm.h) are used
2. The compiler may make different decisions about return value handling
3. The generated code doesn't include the epilogue to write to the result pointer

## Fix: Assembly Implementation in libgcc1.s

Added hand-written `___mulsi3` to `gcc/config/m6809/libgcc1.s` and `_mulsi3` to LIB1ASMFUNCS in t-m6809.
Also added `_muldi3` to LIB2FUNCS_EXCLUDE to prevent the broken libgcc2.c version from being linked.

### ABI Details Discovered

The m6809 ABI has an asymmetry in how 32-bit values are laid out:

**Arguments on stack** (pushed high-word first, so low word ends up at lower address):
```
S+2 = low word   (e.g., 6 for input value 6)
S+4 = high word  (e.g., 0 for input value 6)
```

**Result area** (caller expects big-endian order):
```
X+0 = high word  (should be 0 for result 42)
X+2 = low word   (should be 42 for result 42)
```

The assembly implementation handles this correctly by:
1. Reading arguments from stack with low word at lower offset
2. Writing result to sret pointer with high word at offset 0, low word at offset 2

## Debugging Commands

```bash
# Run test suite
nix develop -c uv run tests/run_tests.py multiply_long_vars

# Check generated assembly
nix develop -c sh -c 'm6809-unknown-none-gcc $M6809_CFLAGS -S -Os tests/cases/multiply_long_vars.c -o -'

# Compare divmod.c assembly (working)
nix develop -c sh -c 'm6809-unknown-none-gcc $M6809_CFLAGS -Os -S $GCC6809_SRC/gcc/config/divmod.c -o -'

# View libgcc.a contents (DFAR format)
LIBGCC=result/lib/gcc/m6809-unknown-none/4.3.6/libgcc.a
grep -A 200 "^L0 _muldi3.o" $LIBGCC

# Run trace script
nix develop -c uv run tests/debug_mulsi3.py
```

## Related Tests
- `multiply` (16-bit): PASS - uses `_mulhi3` from libgcc1.s
- `multiply_int_vars` (16-bit): PASS - uses `_mulhi3`
- `long_div` (32-bit): PASS - uses `___divsi3` from divmod.c
- `long_mod` (32-bit): PASS - uses `___modsi3` from divmod.c
- `multiply_long_vars` (32-bit): PASS - uses `___mulsi3` from libgcc1.s (FIXED)
