# arm64-darwin.patch

Fixes for building and running GCC 4.3.6 on macOS ARM64 (Apple Silicon).

## Root Cause: ARM64 Variadic Function ABI Mismatch

GCC 4.3.6 uses a variadic typedef for instruction generator functions:

```c
// gcc/recog.h line 219
typedef rtx (*insn_gen_fn) (rtx, ...);
```

But the actual generator functions are non-variadic:

```c
// generated from m6809.md
rtx gen_movsi(rtx operand0, rtx operand1)  // 2 args, NOT variadic
```

**On x86-64, this works by accident** - arguments go in registers regardless of variadic flag.

**On ARM64, this is a critical ABI mismatch:**
- Non-variadic: all arguments in registers x0-x7
- Variadic: named args in x0-x7, variadic args on STACK

When calling `GEN_FCN(code)(x, y)` through the variadic typedef, x goes in x0 but y goes on the stack. The callee expects y in x1 and reads garbage instead.

## Changes

### 1. GEN_FCN Typed Macros (core fix)

**Files:** `gcc/optabs.h`, `gcc/optabs.c`, `gcc/expr.c`, `gcc/expmed.c`, `gcc/builtins.c`

Added typed function pointer casts that tell the compiler exactly how many arguments each call takes:

```c
typedef rtx (*insn_gen_fn_2) (rtx, rtx);
#define GEN_FCN_2(CODE) ((insn_gen_fn_2) GEN_FCN(CODE))
```

Then replaced ~50 `GEN_FCN()` calls with `GEN_FCN_N()` variants.

### 2. host-darwin.c PCH Buffer

**File:** `gcc/config/host-darwin.c`

- Disabled 1GB `pch_address_space` static buffer (causes address aliasing on ARM64)
- Added missing `host_hooks` symbol (link error without it)

### 3. movsi Expander

**File:** `gcc/config/m6809/m6809.md`

Added 32-bit move pattern. The m6809 is 16-bit so this splits into two HImode moves. Without this, `init_set_costs()` crashes trying to emit SImode moves.

### 4. Disable fpic and FPBIT

**File:** `gcc/config/m6809/t-m6809`

- Removed `fpic` from multilib options (causes ICE with subreg into pre-dec memory)
- Disabled `FPBIT` floating-point library (triggers backend bugs the m6809 can't handle)

### 5. Assembler Format Warning

**File:** `as-5.1.1/asxmak/darwin/build/makefile`

Added `-Wno-format-security` (modern compilers error on format string issues).

---

# indirect-call-fix.patch

Fixes indirect function calls clobbering the X register when called after setjmp.

## Problem

When calling a function pointer stored in a variable, GCC would load the address into X, then emit a `JSR ,X` instruction. But if the call was in a setjmp context, the value in X could be clobbered by register restoration before the JSR executed.

## Fix

**File:** `gcc/config/m6809/m6809.c`

Modified `m6809_output_function_call()` to use a safer pattern for indirect calls:
1. Push X register onto stack
2. JSR through stack-indirect addressing `[,S++]`

This ensures the target address isn't held in a register across any potential interference.

---

# mulsi3-fix.patch

Fixes 32-bit multiplication returning 0.

## Problem

`___mulsi3` from libgcc2.c doesn't write the result to the hidden result pointer passed in the X register. The function computes the correct result internally but fails to store it to the memory location expected by the caller.

This happens because libgcc2.c is compiled through GCC's internal build process with different headers (tconfig.h, tm.h) that don't properly configure the struct return handling for the m6809 backend.

## Fix

**Files:** `gcc/config/m6809/libgcc1.s`, `gcc/config/m6809/t-m6809`

1. Added hand-written `___mulsi3` assembly implementation to libgcc1.s
2. Added `_mulsi3` to LIB1ASMFUNCS in t-m6809
3. Added `_muldi3` to LIB2FUNCS_EXCLUDE to prevent the broken libgcc2.c version from being linked

The assembly implementation correctly handles the m6809 ABI:
- Arguments on stack with low word at lower address
- Result written to sret pointer with high word at offset 0, low word at offset 2
