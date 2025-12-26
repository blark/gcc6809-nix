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
