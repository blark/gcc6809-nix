# Review record: libgcc1.s 32-bit and 16-bit multiply

Base: `1d1a0de`, GCC source `e401b3bc8b7a100218185683e7d36c100ef9d4b6`
plus `patches/mulsi3-fix.patch` (`gcc/config/m6809/libgcc1.s`), Beads task
gcc6809-na9.

## Scope and status

Tests only; no implementation change. `___mulsi3` and `_mulhi3` passed
every check on the toolchain built from `1d1a0de`, so nothing in the
helpers was reproduced or fixed.

One adjacent compiler bug was found and is recorded as an XFAIL case
(`mulqihi3_signed.c`, see "Bugs found"): it is in the `mulqihi3` insn
pattern of `m6809.md`, not in a helper.

Since fixed: the compiler fix (890569a) removed that pattern and the
XFAIL, and the flake's emulator now sign-extends correctly in `SEX`
(ae74065). See [SIGNED_MUL.md](SIGNED_MUL.md). The rest of this file
records the review as it was at `1d1a0de`.

The helpers under test are `___mulsi3` (32 x 32 -> low 32 bits, added by
`patches/mulsi3-fix.patch` to replace the libgcc2 `__muldi3` that never
stored its result) and `_mulhi3` (16 x 16 -> low 16 bits). GCC emits
`___mulsi3` for every `long` and `unsigned long` multiply of two
variables and `_mulhi3` for 16-bit variable multiplies; both are shared by
the signed and unsigned types because the low bits of a two's-complement
product do not depend on signedness. Multiplies by small constants are
open-coded (shifts, adds, `mulqihi3`).

## Helper contract

Established from the source and from the code GCC generates (`u * v`
compiled at -O2), then confirmed by the checks below.

`___mulsi3`:

- Both operands on the stack, each as a big-endian 32-bit value (high
  word at the lower address). GCC pushes the first operand, then the
  second, so on entry the second operand is at `2,s` (high word) / `4,s`
  and the first at `6,s` / `8,s`. The order does not affect the product.
- X holds a pointer to a 4-byte result area; the product is stored there
  big-endian (`0,x` high word, `2,x` low word). Apart from its own
  14-byte stack frame, it writes only those 4 bytes (the review script
  checks 8 guard bytes on each side of them).
- After `rts`, S is the entry S + 2 (the return address is popped); the
  caller then removes the 8 argument bytes.
- On return X still holds the result pointer (`puls x,pc` restores it).
  GCC does not rely on this: it reloads the product from the result area.
- D and CC are clobbered; Y, U and DP are untouched. Uses 14 bytes of
  stack below the return address, calls nothing.
- No division, no shifts, no `SEX`: four 8 x 8 `MUL`s for the low words,
  three each for the two cross products, added with carries.
  Product bits above 31 are discarded, so the result is
  `(u * v) mod 2^32` for every operand pair.

`_mulhi3`:

- Left operand in X, right operand at `2,s` (the caller pops it), product
  in X as `(a * b) mod 2^16`. Three 8 x 8 `MUL`s.
- After `rts`, S is the entry S + 2; the caller removes the right operand.
  D clobbered; Y, U and DP untouched.

## Evidence

Five compiled C cases in `tests/cases`, run at -O0, -Os and -O2 by the
normal suite:

- `mulsi3_wrap.c`: 63 `unsigned long` pairs with products needing 31..64
  bits: 0, 1, 0xFFFFFFFF on either side and squared, powers of two whose
  product needs 31..63 bits, 0xFFFF and 0x10000 squared, 0x7FFFFFFF and
  0x80000000 against small multipliers, byte patterns (0x00FF00FF,
  0x80808080, 0x01010101, 0xAAAAAAAA...) that carry through each of the
  helper's partial products, and both operand orders.
- `mulsi3_random.c`: 96 uniform 32-bit pairs from `random.Random(6809)`,
  each checked in both operand orders.
- `mulsi3_signed.c`: 26 `long` products that fit in 32 bits with negative
  operands, LONG_MIN and LONG_MAX, so signed operands go through the same
  helper without invoking signed-overflow behaviour.
- `mulhi3_wrap.c`: 42 `unsigned int` pairs with products overflowing
  16 bits (0xFFFF squared, 256 * 256, 0x8000 * 3, ...).
- `mulqihi3_signed.c` (XFAIL): `signed char * signed char` with negative
  operands, see below.

All expected values were computed on the host with Python
(`(u * v) & 0xFFFFFFFF`), not with the toolchain. The operands are
`volatile` so the helper is reached at -O2 (checked in the generated
assembly), and no case sign-extends a negative `int` to `long`, so the
6809 `SEX` instruction is not on any path (see "Emulator"). Each case was
checked to fail on a deliberately wrong entry (it reports that entry's
index).

`run_mulsi3_review.py` links the real helpers from `libgcc.a` and calls
them as GCC does, checking the product, S, the Y/U/DP canaries and, for
`___mulsi3`, X and 8 guard bytes on each side of the result area:

- `___mulsi3` edge grid: all pairs of 45 edge operands (0, 1, 2, 3,
  0x7F..0x101, 0x7FFF..0x10001, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, byte
  patterns, 46341, 65537, ...): 2,025 calls;
- `___mulsi3` byte positions: every byte value at each of the four byte
  positions of `u` times every byte value at each position of `v`
  (16 x 65,536 = 1,048,576 calls), which drives every 8 x 8 partial
  product with all 65,536 byte pairs. With one non-zero byte per
  operand, the carries between partial products are not all exercised:
  those come from the edge grid and the random pairs (for example,
  0xFFFF x 0xFFFF fails if the middle `adca #0` is replaced by `lda #0`,
  while the byte-position grid still passes);
- `___mulsi3` random: 200,000 pairs from `random.Random(6809)`, every
  second pair with random bytes cleared so zero bytes appear at every
  position;
- `_mulhi3`: every 16-bit left operand x 16 right operands
  (`1 2 3 0x7F 0xFF 0x100 0x101 0x7FFF 0x8000 0x8001 0xFFFE 0xFFFF 0x5555 0xAAAA 0x1234 46341`):
  1,048,576 calls, plus 100,000 random pairs.

A mutated reference (`u * v + (u >> 31)`) makes the script report
failures for every operand with bit 31 set, so it does detect wrong
results.

## Bugs found

`mulqihi3` in `gcc/config/m6809/m6809.md` (not a helper): the pattern
matches `(mult:HI (sign_extend:HI QI) QI)` and emits `lda %2; mul`, but
`MUL` is unsigned. At -Os and -O2 GCC uses it for
`signed char * signed char`, so `(-1) * (-1)` returns 0xFE01 (255 * 255)
instead of 1. Reproduction:

```c
int mulqi(signed char a, signed char b) { return a * b; }   /* noinline */
int main(void) { return mulqi(-1, -1); }                    /* 0xFE01, want 1 */
```

At -O0 GCC sign-extends both operands (`SEX`) and calls `_mulhi3`, which
is correct code; that path fails only on the emulator (below).
`umulqihi3` (zero-extended operands) is correct. A fix would drop the
signed pattern or correct the product for negative operands; it needs a
GCC rebuild and is out of scope here. `tests/cases/mulqihi3_signed.c` is
marked XFAIL until then. (Fixed in 890569a; see [SIGNED_MUL.md](SIGNED_MUL.md).)

## Emulator

gcc6809-877: the flake's MC6809 0.6.0 does not set A to 0xFF in `SEX`
when B is negative. Neither helper executes `SEX`, and none of the new
cases compiles to one (checked with `grep sex` on the assembly at all
three levels: `unsigned long` operands and `long` literals need no
sign extension), so the results above are not affected by that defect.
`mulqihi3_signed.c` is the exception: at -O0 its failure is the emulator's,
at -Os/-O2 it is the compiler's. The emulator's `MUL` was checked against
the data sheet (unsigned 8 x 8 -> D, C = bit 7 of B).

## Results

Observed on macOS ARM64 with the flake's MC6809 0.6.0 emulator, toolchain
built from `1d1a0de`:

| Check | Result |
|---|---:|
| `tests/run_tests.py mul` (11 cases x 3 levels) | 30 pass, 3 xfail |
| full suite `nix run .#test` | 189 pass, 0 fail, 3 xfail (64 cases x 3 levels) |
| `run_mulsi3_review.py` `___mulsi3` edge grid | 2,025 pass |
| `run_mulsi3_review.py` `___mulsi3` byte positions | 1,048,576 pass |
| `run_mulsi3_review.py` `___mulsi3` random | 200,000 pass |
| `run_mulsi3_review.py` `_mulhi3` sweep + random | 1,148,576 pass |

The full script (2,399,177 calls) takes about 40 s on 8
processes; `--quick` (edge grid, byte positions (0,0) and (3,3) only, 5,000 random
pairs) runs about 400,000 calls, `--random N` and `--seed S`
change the random batch.

Limitations: emulator execution, not hardware; the default ABI only (the
`mdret` multilib's `libgcc.a` was not run); `___mulsi3` is exhaustive per
byte position, not over all 2^64 operand pairs.

## Reproduce

```sh
nix build --no-write-lock-file .#toolchain
nix build --no-write-lock-file --impure --out-link /tmp/py --expr "
  let f = builtins.getFlake \"$PWD\";
      pkgs = f.inputs.nixpkgs.legacyPackages.aarch64-darwin;
  in pkgs.python3.withPackages (_: [ f.packages.aarch64-darwin.mc6809 ])"
/tmp/py/bin/python3 -B tests/run_tests.py mul
/tmp/py/bin/python3 -B tests/review/run_mulsi3_review.py
```
