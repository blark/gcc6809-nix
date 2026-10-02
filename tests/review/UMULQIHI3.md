# Unsigned byte-product RTL: gcc6809-hjh

Base: main `156e116`, including `mulqi3-narrow.patch`. GCC source:
`e401b3bc8b7a100218185683e7d36c100ef9d4b6`; default 16-bit-int ABI.

## Defect and fix

The native `umulqihi3` pattern had an HImode multiplication with only its
first QI operand zero-extended. Its second operand was a bare QI value.
For constants, QI sign normalization produced negative HI factors: unsigned
200 became `const_int -56`, 255 became -1, and 129 became -127. `LDA; MUL`
uses their unsigned byte bit patterns. The RTL and the full hardware
product therefore disagreed, although the low byte still agreed.

It is a C wrong-code bug. When the compiler knows the byte's value, it
folds the product from the RTL: in `tests/cases/umulqihi3_fold.c`,
`if (v.s == -3) return v.u * 200u;` returns 51368 (253 * -56) instead of
50600 at -O2, -O3 and -Os before the fix (`ldx #-14168`), and 50600 at every
level after it (gcc6809-n9p). `umulqihi3_factors.c` passes on both compilers;
`umulqihi3_fold.c` and the RTL checker fail before the fix.

`patches/umulqihi3-operands.patch` separates expansion from recognition:

- The `umulqihi3` expander explicitly zero-extends both nonconstant bytes.
- The register/memory instruction retains the B input constraint and
  same-byte `TFR B,A; MUL` alternative from the narrow-product fix.
- For a constant second input, the expander masks the sign-normalized QI
  value to 0..255 and emits a separate constant instruction. That pattern
  has an HI constant operand and rejects values outside the unsigned-byte
  range. The old signed `K` constraint is not used for this HI factor.

No generic reload, runtime helper, calling convention, or shared runner
changes. Signed full-width byte products still widen before ordinary HI
multiplication. Narrow signed products may use unsigned MUL because only
the low byte is observable. The HI output describes D; A is a separate
fixed register and is never allocated.

## Regression contracts

`check_umulqihi3_rtl.py` compiles `mulqi3_narrow.c` and
`umulqihi3_factors.c` at `-O0 -O1 -O2 -O3 -Os` and reads expand dumps.
For a native HI product with a zero-extended byte first operand, it
requires the second operand to be another zero-extended QI value or a
constant in 0..255. It rejects bare QI operands and negative/oversized HI
constants. It also requires native-product and immediate-factor coverage;
missing dumps, compilation errors, or missing coverage fail the check.
This is a targeted native-pattern check, not a general GCC RTL verifier.

`test_umulqihi3_rtl_checker.py` has eight unit tests covering accepted
register/memory/constant forms, rejected bare-QI and bad-constant forms,
wrong extension modes, ordinary HI products, quoted parentheses, and
truncated dumps.

`umulqihi3_factors.c` checks all 256 input bit patterns for low-byte and
full-HI products by 200, 255, and 129, a signed low-byte product by -56,
and a variable unsigned HI product. Eight comparisons per input:
2,048 comparisons at each optimization level. Expected values come from
host-computed literal tables, not target multiplication. Unsigned HI
products explicitly promote to `unsigned int`, avoiding signed-int16
overflow. The signed product by -56 is in range; conversion from unsigned
to signed char uses this target's byte interpretation.

## Verification

| Check | Baseline | Fixed |
|---|---:|---:|
| Generated native RTL, five levels | 53 products, 24 constants; **53 errors** | Same coverage; **0 errors** |
| New C factor case, five levels | 5 pass | **5 pass** |
| Full C suite, five levels | Not repeated | **350 pass; 0 failures; no XFAIL** |
| Exhaustive narrow/square compiled functions | Not repeated | **1,317,120 pass; 0 failures** |
| Exhaustive signed/mixed/unsigned HI compiled functions | Not repeated | **1,315,840 pass; 0 failures** |
| Existing 16/32-bit multiply-helper matrix | Not repeated | **2,399,177 pass; 0 failures** |
| RTL-checker unit tests | Not applicable | **8 pass** |
| Existing divide/modulo matrix, including abort/core calls | Not repeated | **4,719,182 pass; 0 failures** |
| Existing bit-helper matrix/exhaustive sweeps | Not repeated | **1,001,762 pass; 0 failures** |
| Exhaustive longjmp and C regressions | Not repeated | **65,536 calls and 15 C runs pass** |

The GCC, newlib, and joined toolchain build succeeded. Runtime verification
uses the flake's SEX-corrected MC6809 emulator, not hardware. Exhaustive
function-input tests do not exhaust all C programs, ABIs, or CPU states.
The lock file and shared `tests/run_tests.py` are unchanged. A temporary
adversarial constant sweep also passed 655,360 compiled calls: all 256
input bytes and factors in low-byte signed and full-HI unsigned functions
at all five levels. This temporary probe is additional evidence, not part
of the permanent regression drivers.

Independent read-only review: **ACCEPT**, with no introduced compiler or
Nix defects. The reviewer repeated baseline/fixed RTL checks, five focused
C runs, 2,250 narrow and 2,200 signed/HI edge calls, and eight checker unit
tests; recomputed every golden row; and passed 7,425 extra adversarial
compiled calls while inspecting 218 RTL dumps. All-system flake checking
and touched derivation-path evaluation passed. Existing flake formatting
debt is unchanged. The targeted checker skips products without the first
zero extension and does not guarantee exact per-function coverage counts;
this nonblocking limitation was explicitly reviewed. No merge is authorized.

## Reproduce

Run from the candidate worktree with Nix flakes enabled. Use `path:$root`
so new, untracked patch/test files are included. Allow 600 seconds for a
compiler/library build. These commands do not modify the lock.

```sh
root="$PWD"
ro='--no-write-lock-file --option allow-import-from-derivation false'
system="$(nix eval $ro --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-umulqihi3.XXXXXX)"
nix build $ro "path:$root#toolchain" --out-link "$work/fixed"
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"path:$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
# GCC alone suffices for the baseline RTL check; no baseline libc is needed.
nix build $ro --impure --out-link "$work/baseline-gcc" --expr "
  let f = builtins.getFlake \"path:$root\";
  in f.packages.$system.gcc6809.overrideAttrs (old: {
    patches = builtins.filter
      (p: baseNameOf p != \"umulqihi3-operands.patch\") old.patches;
  })"
export GCC6809_OPT='-O0 -O1 -O2 -O3 -Os'
unset M6809_LIBC M6809_CFLAGS
# Expected exit 1 and 53 RTL errors. Continue after this expected failure.
GCC6809_TOOLCHAIN="$work/baseline-gcc" "$work/python/bin/python3" -B \
  tests/review/check_umulqihi3_rtl.py
export GCC6809_TOOLCHAIN="$work/fixed"
"$work/python/bin/python3" -B tests/review/check_umulqihi3_rtl.py
"$work/python/bin/python3" -B tests/review/test_umulqihi3_rtl_checker.py
"$work/python/bin/python3" -B tests/run_tests.py
"$work/python/bin/python3" -B tests/review/run_mulqi3_review.py --exhaustive
"$work/python/bin/python3" -B tests/review/run_signed_mul_review.py --exhaustive
"$work/python/bin/python3" -B tests/review/run_mulsi3_review.py --jobs 8
```
