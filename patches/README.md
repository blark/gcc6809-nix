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

# movsi-fix.patch

Fixes the two 32-bit move bugs in the `movsi` expander that arm64-darwin.patch
added to `gcc/config/m6809/m6809.md`.

## 1. Long arguments pushed with their words swapped

A push writes downward: the half pushed first ends up at the higher address.
The expander pushed the high half first, so a `long` argument was stored with
its low word at the lower address, while every callee reads a long from memory
big-endian (high word at the lower address). Callers and callees compiled by
the same compiler therefore disagreed: `add1(x, y)` received both halves of
each argument swapped. libgcc's 32-bit multiply and divide happened to work
(they hand the words on to another call, which swapped them back); its
variable shifts did not, and lua-6809 computed `2^10` as 0.

The fix pushes the low half first.

## 2. 32-bit constants crash the compiler

The constant was split with `GEN_INT (half & 0xFFFF)`. A HImode constant must
be sign-extended, so any half >= 0x8000 (`-1L`, `40000UL`, `0x8000L`) produced
an insn `movhi` does not recognize ("unrecognizable insn ... internal compiler
error: in extract_insn"). The optimizer creates such constants itself
(`x = 0; x--` becomes `-1`). `gen_int_mode (half, HImode)` fixes it.

A constant pushed as an argument (`add1(0x12345678L, 1L)`) fell through to
`simplify_gen_subreg` of the push destination and produced
`(subreg:HI (mem:SI (pre_dec:HI s)) 2)`, which nothing recognizes. Constants
now go through the same push path as registers.

The pop case (first pop reads the high half) and overlapping register moves
are handled while at it.

---

# indirect-call-stack-offset.patch

Fixes indirect calls whose function pointer lives in a stack slot or is
reached through a register, when arguments have been pushed for the call.

## Symptom

`p->f(a, 3)` compiled to `jsr [2,y]` although `f` is at offset 0 in the
struct; a function pointer spilled to the stack was called through `jsr [2,s]`
or `jsr [12,s]` with the offset of the slot *before* the arguments were pushed.

## Cause

Two things:

**gcc/reload.c** (generic, but only visible on targets with memory-indirect
addressing such as `jsr [n,s]`): reload's first pass sees a call address of the
form `(mem (reg pseudo))` where the pseudo has been spilled to a stack slot.
`find_reloads_address` decides that the slot's address is itself valid as an
indirect address and returns "no reload needed", so the insn is marked as
needing neither reloads nor operand changes. The re-eliminated slot address
(which accounts for the pushed arguments) is only substituted in the final
pass, and the final pass skips `find_reloads` for such insns. The pseudo is
then replaced by `reg_equiv_mem`, whose address holds the elimination offset at
function entry, i.e. the slot offset before any pushes. The patch makes
`find_reloads` report an operand change in that case so that the final pass
revisits the insn and substitutes the correct address.

**gcc/config/m6809/m6809.c** `print_operand_address`: the port papered over the
`(mem (reg s))` case of the above by adding the pushed-argument byte count to
any `[,reg]` call operand. That was only right for `[,s]` and only when no
earlier call's arguments were still on the stack, and it was wrong for every
other register (`jsr [2,y]` above). With reload fixed the compensation is
removed.

The earlier indirect-call-fix.patch (`ldy n,s` / `jsr ,y` in the output
routine) attacked the same symptom; it clobbered Y and was dropped.

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

The assembly implementation follows the m6809 ABI:
- Arguments on the stack, each long big-endian (high word at the lower address,
  as movsi-fix.patch now pushes them; the first version of this file read them
  in the swapped order the buggy compiler produced)
- Result written to the sret pointer with high word at offset 0, low word at offset 2

---

# newlib-m6809.patch

Brian Dominy's m6809 port of newlib 1.15.0 (`newlib/libc/machine/m6809`,
`libgloss/m6809`, build script `build/newlib.6809`). Hand-written assembly:
`setjmp.S` only; everything else is C.

---

# newlib-longjmp-zero.patch

`longjmp(env, 0)` now makes `setjmp` return 1, as C99 7.13.2.1p4 requires.

## Problem

**File:** `newlib/libc/machine/m6809/setjmp.S`

`_longjmp` loaded `val` from the stack (`ldd 2,s`) and returned it in X
unchanged, so `longjmp(env, 0)` made `setjmp` return 0 a second time and
`if (setjmp(env) == 0) { ... longjmp(env, 0); }` re-entered its first-time
path.

## Fix

Right after `ldd 2,s`:

```asm
	bne longjmp_value_ready
	ldd #1                ; ISO C: longjmp(env, 0) returns 1
longjmp_value_ready:
```

`LDD` sets Z from the full 16-bit value, so every nonzero `val` (including
`0x0100` and `0x00FF`) is unchanged. D is the only register touched, CC is
restored from the jump buffer afterwards, and the jump-buffer layout, the
calling convention and the rest of the routine are the same. `_longjmp`
grows by 5 bytes (58 to 63 bytes for the module). `bne` + `incb` would do
the same in 3 bytes (D == 0 implies B == 0); the `ldd #1` form was kept as
reviewed for readability.

Tests: `tests/cases/longjmp_zero.c`, `longjmp_values.c`, `longjmp_nested.c`
(all fail with the old libc at every optimization level), plus
`tests/review/run_longjmp_review.py --exhaustive`, which runs the linked
`_longjmp` for all 65,536 values of `val` and checks X, Y, U, S, DP, CC and
PC. Review record: `tests/review/LONGJMP.md`.

---

# signed-mulqi-fix.patch

Removes the invalid signed `mulqihi3` pattern from `gcc/config/m6809/m6809.md`.
The 6809 `MUL` instruction is unsigned: selecting it for signed byte products
made `(-1) * (-1)` return `0xfe01` instead of 1. GCC now widens signed
operands before HImode multiplication. The unsigned `umulqihi3` pattern,
runtime helpers and ABI are unchanged.

The compiled regression is `tests/cases/mulqihi3_signed.c`, now without XFAIL.
`tests/review/run_signed_mul_review.py --exhaustive` checks all byte pairs
in four signedness combinations, plus constant multipliers, at five
optimization levels. Use the separately corrected MC6809 emulator so its
old `SEX` defect cannot mask compiler results. Evidence and reproduction:
`tests/review/SIGNED_MUL.md`.
