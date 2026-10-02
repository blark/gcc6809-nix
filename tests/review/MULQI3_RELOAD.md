# Narrow byte multiplication: reload ICE

Scope: GCC source `e401b3bc8b7a100218185683e7d36c100ef9d4b6`, default
16-bit-int ABI. Compiler ICE task: `gcc6809-l5y`. Baseline main: `cf92790`.
Tests-first commits: `e125df1`, `470de37`, `9b11a62`, `95de82a`.

## Reproduction and cause

After removing the incorrect signed widening `mulqihi3` pattern, Anachron8
Classic Tetris and Super Tetris fail in `try_rotate` at `-Os`:

```text
unable to find a register to spill in class 'A_REGS'
(set (reg:HI 1 x) (subreg:HI (reg/v:QI ... [ dir ]) 0))
```

Both actual sources at anachron8-sw `5c28cd2` reproduce, while the reference
compiler before the signed-MUL correction compiles them. Manual reduction
also finds a three-line case; a loop is not necessary:

```c
extern signed char input(void);
unsigned char product(signed char factor)
{ return (unsigned char)(input() * factor); }
```

The backend has no `mulqi3`. When optimizing a product whose result is
truncated to a byte, `gcc/optabs.c:expand_binop` widens it to `mulhi3` with
`widen_operand` and paradoxical HI subregs of QI operands. Their upper bits
are unspecified, which is legitimate because only the low result byte is
needed. Reload cannot put a byte pseudo surviving a call into this target's
address-register class, `A_REGS`; this is not accumulator A's class.
The initial RTL expansion already contains those subregs.

## Fix

`patches/mulqi3-narrow.patch` supplies a QImode multiplication expander. It
calls the existing unsigned widening `umulqihi3` into a fresh HI temporary,
then copies the low byte. The HI output tells reload that MUL writes all of
D, not only the byte result. MUL also overwrites A, which this port models as
a separate hard register; that needs no clobber of its own because A is a
fixed register the allocator never assigns.

For any byte bit patterns a and b, signed and unsigned interpretations
differ by multiples of 256, so their products agree modulo 256. This does
**not** permit unsigned MUL for signed products whose full HI result is
needed: `signed-mulqi-fix.patch` remains applied and `mulqihi3` remains
removed. No generic reload, runtime helper, calling convention, or shared
test-runner changes.

Independent review rejected an initial candidate that reused the old
unsigned pattern unchanged: `x * x` caused a new constraint ICE after
reload coalesced the operands. Three self-product regressions were added
before correcting it. The native pattern now requires its first operand
in B, rather than the broader q class, and accepts identical operands with
a matching constraint. That alternative emits `tfr b,a; mul`; the other
retains `lda operand; mul`. Both still describe the entire D output.
Full-HI signed and unsigned square oracles also verify this boundary.

## Tests and results

- `signed_mul_register_pressure.c`: reduced rotation loop with a byte live
  across calls, two products, positive/negative factors, observable updates.
- `mulqi3_narrow.c`: four input signedness combinations, volatile source
  read through a noinline call, factor surviving the call, unsigned-byte
  result. Unsigned/unsigned multiplication explicitly promotes to unsigned
  int to avoid 16-bit signed overflow; all signed/mixed products fit in int.
  Signed/unsigned parameter squares, a single-read volatile square and two
  full-HI squares exercise operand coalescing, not just numerically equal
  values from independent sources.
- `run_mulqi3_review.py`: links the actual compiled functions and checks
  every byte pair plus every byte input for five square functions against
  a host integer oracle. Narrow results are B; full-HI results are X. Shared
  `run_signed_mul_review.Machine` checks PC, S, Y/U and stack canaries;
  the driver also checks that the source is unchanged. Requires sibling
  review driver and harness; copying this file alone is unsupported.

| Check | Baseline | Fixed |
|---|---:|---:|
| Two new C cases, five optimization levels | 0 pass, 10 compile failures | 10 pass |
| New narrow-product/square oracle, five levels | compile fails | 1,317,120 pass |
| Existing full-HI byte-product oracle | 1,315,840 pass | 1,315,840 pass |
| Full C suite: main plus these two cases | 335 pass, 10 failures | 345 pass |
| Existing multiply helper matrix | previously accepted | 2,399,177 pass |
| Existing divide/modulo matrix | previously accepted | 4,719,182 pass |
| Existing bit-helper matrix | previously accepted | 1,001,762 pass |
| Exhaustive longjmp ABI check | previously accepted | 65,536 pass |

The combined baseline suite was rerun with the same corrected emulator:
335 passes and ten compile failures. Optimizations: `-O0 -O1 -O2 -O3 -Os`.
Exhaustive byte operands apply only to the four
binary functions and five square functions, not every expression, register
state or ABI.
Two temporary mutations of the compiled `-Os narrow_ss` MUL are detected:
replacing it with NOP fails 74/100 edge calls; INCB fails 97/100. Each
mutation preserves the instruction boundary and caller/return flow.

Independent read-only rereview accepted the corrected patch, including its
same-register alternative, immediate operands and preserved signed-HI
libcalls. It reran 2,250 new edge calls, 2,200 existing HI edge calls and
three focused C cases at all five levels. Both worktree and staged patch
application passed. All-system Nix evaluation and touched package drvPath
checks passed; the lock stayed unchanged. The reviewer did not independently
repeat the exhaustive sweeps, external game builds or hardware tests.

The original build scripts now compile, assemble and link Classic Tetris
for maps v1/v2 and Super Tetris for v2, with no warnings/errors. Super
Tetris's optional music file was absent; the build produces its documented
silent-game image. This verifies builds, not gameplay or physical hardware.
Only a temporary Anachron8 clone was used; no pin or source was changed.

## Reproduce

Run from this branch on aarch64-darwin; allow at least 600 seconds per build.
Nix flakes must be enabled. No lock update is needed.

```sh
root="$PWD"
ro='--no-write-lock-file --option allow-import-from-derivation false'
system="$(nix eval $ro --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-mulqi3.XXXXXX)"
nix build $ro .#toolchain --out-link "$work/fixed"
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
nix build $ro --impure --out-link "$work/baseline-gcc" --expr "
  let f = builtins.getFlake \"$root\";
  in f.packages.$system.gcc6809.overrideAttrs (old: {
    patches = builtins.filter
      (p: baseNameOf p != \"mulqi3-narrow.patch\") old.patches;
  })"
# Expected compiler failure, exit 1. Retain the signed widening correction.
"$work/baseline-gcc/bin/m6809-unknown-none-gcc" -Os -S \
  tests/cases/mulqi3_narrow.c -o "$work/baseline.s"
export GCC6809_OPT='-O0 -O1 -O2 -O3 -Os'
unset M6809_LIBC M6809_CFLAGS
export GCC6809_TOOLCHAIN="$work/fixed"
nix run $ro .#test
"$work/python/bin/python3" -B tests/review/run_mulqi3_review.py --exhaustive
"$work/python/bin/python3" -B tests/review/run_signed_mul_review.py --exhaustive
```

For actual-program build verification in a temporary checkout:

```sh
git clone https://git.sherwood.haus/blark/anachron8-sw.git "$work/games"
git -C "$work/games" checkout --detach 5c28cd287a5d22dd8140ff15e2baf4a2e0eb93db
cd "$work/games"
python3 tools/gen_hw.py --check
nix develop $ro "$root" --command bash -c '
  MAP=v1 bash tetris/build_tetris.sh &&
  MAP=v2 bash tetris/build_tetris.sh &&
  MAP=v2 bash stetris/build_stetris.sh'
```
