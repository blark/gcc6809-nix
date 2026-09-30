# Signed byte multiplication: gcc6809-6d6

GCC source: `e401b3bc8b7a100218185683e7d36c100ef9d4b6`, default
16-bit-int ABI. Tests-first commit: `e882557`.

## Compiler defect and fix

The `mulqihi3` instruction pattern in `gcc/config/m6809/m6809.md` matches
a signed widening multiplication but emits `lda operand; mul`. The 6809
`MUL` instruction multiplies **unsigned** A and B. Thus compiled
`signed char` multiplication such as `(-1) * (-1)` produces `0xfe01`
instead of 1 at `-O1`, `-O2`, `-O3` and `-Os`. Multiplication by the
constants 3 and -3 also selects the wrong pattern.

`patches/signed-mulqi-fix.patch` removes that pattern and its incorrect
TODO about merging signed/unsigned extensions. GCC then widens signed
operands before ordinary HImode multiplication. The unsigned `umulqihi3`
pattern is unchanged: the optimized unsigned-byte function still uses
native `MUL`. No calling convention or hand-written runtime helper changes.
Signed code may be larger/slower than the incorrect shortcut; no cycle or
size benchmark is claimed.

This is distinct from **gcc6809-877**, the MC6809 emulator's broken `SEX`
instruction. The emulator fix is required for valid signed-extension code.
All compiler comparisons below use the same corrected emulator. The
standalone driver rejects an emulator that fails a raw `SEX` preflight;
it never replaces instruction behavior at runtime.

## Regressions

`tests/cases/mulqihi3_signed.c` now has four noinline binary functions:
signed/signed, signed/unsigned, unsigned/signed, and unsigned/unsigned.
The last explicitly casts to `unsigned int`, avoiding signed integer
promotion overflow for `255 * 255`. All signed and mixed products fit in
16-bit `int`. Four additional functions multiply a signed byte by
3, -3, 255 and 256; these are also in range, including `-128 * 256`.

The normal C test uses 100 host-computed binary golden rows and 10
constant rows (440 comparisons). Operands are volatile, expected products
are constants, and the former XFAIL is now a required regression.

`run_signed_mul_review.py` compiles that same C file separately at each
optimization level and links the actual libgcc. It calls the generated
functions directly, not stand-in assembly implementations:

- first byte argument in B, second byte at entry S+2, result in X;
- Y/U preserved, S returns to entry S+2, return PC reaches its sentinel;
- canaries just above the argument and 256 bytes below entry S;
- host integer oracle with explicit signed/unsigned byte interpretation;
- bounded execution; malformed code, timeouts, ABI errors or wrong values
  fail the review.

Default coverage is 2,200 edge calls across five levels. `--exhaustive`
tests all 65,536 byte pairs for each of four signedness combinations, plus
all 256 inputs for each constant, at `-O0 -O1 -O2 -O3 -Os`:
**1,315,840 compiled-function calls**. This exhausts operand values for
those functions, not all C expressions, CPU states, ABIs or memory accesses.

## Evidence

| Check | Original compiler | Patched compiler |
|---|---:|---:|
| Exhaustive compiled byte products | 1,118,728 pass; 197,112 fail | **1,315,840 pass; 0 fail** |
| Full C suite, five levels, XFAIL removed | 331 pass; 4 fail | **335 pass; 0 fail** |

The original compiler passes all tested functions at `-O0`. At each
optimized level it fails 48,895 signed/signed pairs, 128 multiply-by-3
inputs and 255 multiply-by-minus-3 inputs. The mixed and unsigned functions
and the 255/256 constants pass even before the patch.

Additional checks with the rebuilt compiler and libraries:

| Existing review | Passed |
|---|---:|
| 16/32-bit multiply helper matrix | 2,399,177 |
| Divide/modulo: normal + abort + core calls | 4,719,182 |
| Bit-helper edges and exhaustive sweeps | 1,001,762 |
| Exhaustive longjmp | 65,536 |

An independent read-only reviewer accepted the patch and Nix wiring,
checked the C/ABI/oracles, reran all 2,200 edge calls, and inspected `-Os`
and `-O2` assembly: signed/mixed functions widen and call `_mulhi3`, while
unsigned multiplication retains `MUL`. All-system flake evaluation passed;
`flake.lock` and `tests/run_tests.py` are unchanged. Existing flake formatting
debt was not included in this fix. Validation uses an emulator, not hardware.

## Reproduce

Run from this branch with Nix flakes enabled. Allow at least 600 seconds
for each build. The branch includes the separately reviewed emulator fix.

```sh
root="$PWD"
ro='--no-write-lock-file --option allow-import-from-derivation false'
system="$(nix eval $ro --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-signed-mul.XXXXXX)"
nix build $ro .#toolchain --out-link "$work/fixed"
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
# Baseline compiler/libgcc only; the standalone driver does not need libc.
nix build $ro --impure --out-link "$work/baseline-gcc" --expr "
  let f = builtins.getFlake \"$root\";
  in f.packages.$system.gcc6809.overrideAttrs (old: {
    patches = builtins.filter
      (p: baseNameOf p != \"signed-mulqi-fix.patch\") old.patches;
  })"
export GCC6809_OPT='-O0 -O1 -O2 -O3 -Os'
unset M6809_LIBC M6809_CFLAGS
# Expected exit 1 with 197,112 failures; do not let set -e stop the next step.
GCC6809_TOOLCHAIN="$work/baseline-gcc" "$work/python/bin/python3" -B \
  tests/review/run_signed_mul_review.py --exhaustive
# Expected exit 0, all calls pass.
export GCC6809_TOOLCHAIN="$work/fixed"
"$work/python/bin/python3" -B tests/review/run_signed_mul_review.py --exhaustive
nix run $ro .#test
"$work/python/bin/python3" -B tests/review/run_mulsi3_review.py --jobs 8
"$work/python/bin/python3" -B tests/review/run_divmod_review.py --jobs 8
"$work/python/bin/python3" -B tests/review/run_bit_helpers.py --exhaustive
"$work/python/bin/python3" -B tests/review/run_longjmp_review.py --exhaustive
```
