# Review record: libgcc1.s 16-bit divide and modulo

Base: `043e30e`, GCC source `e401b3bc8b7a100218185683e7d36c100ef9d4b6`
(`gcc/config/m6809/libgcc1.s`), Beads task gcc6809-ckk.

## Scope and status

Tests only; no implementation change. Every check passed on the toolchain
as built from `043e30e`, so nothing was reproduced or fixed.

The helpers under test are `_divhi3`, `_modhi3`, `_udivhi3`, `_umodhi3` and
the routines they share, `_seuclid` (signed) and `_euclid` (unsigned).
GCC emits them for every 16-bit `/` and `%` on variables, including `char`
operands after integer promotion (there is no `_divqi3` in libgcc; the
`divqi3` expander in `m6809.md` is never reached). 32-bit division is
C code from `libgcc2` (`udivmodsi4.c`, `divmod.c`) and is out of scope.

## Helper contract

Established from the source and from the code GCC generates (`sdiv` and
friends compiled at -O2), then confirmed by the checks below.

Wrappers (`_divhi3`, `_modhi3`, `_udivhi3`, `_umodhi3`):

- Dividend in X, divisor pushed on the stack (at `2,s` on entry, the
  caller pops it), result in X.
- Y, U and DP are not touched; S is restored.
- Divisor 0: `jmp _abort` with the return address and divisor still on the
  stack. `_abort` never returns. The comment in `libgcc1.s` says "check
  dividend", but the value tested is the divisor.
- Signed results follow C99 6.5.5: the quotient truncates toward zero and
  the remainder takes the dividend's sign.
- `INT_MIN / -1` does not trap: the quotient is `0x8000` (-32768, the
  two's-complement wrap of 32768) and the remainder is 0. This is the
  observed behaviour; it is undefined in C and libgcc documents nothing.

Core routines (`_seuclid`, `_euclid`): push the left operand, load the
right operand into D, call. The quotient replaces the pushed left operand
and the modulus is returned in D. `_seuclid` takes absolute values (as
unsigned, so 0x8000 becomes 32768), runs `_euclid`, and negates the
quotient when the signs differ and the modulus when the dividend was
negative. `_euclid` with a zero divisor never terminates (its prescale
loop waits for bit 15 to become set); only the wrappers guard against it,
so nothing else may call `_euclid`/`_seuclid` with a zero divisor.

## Evidence

Four compiled C cases in `tests/cases`, run at -O0, -Os and -O2 by the
normal suite:

- `divmod_signed.c`: 45 (a, b) pairs covering all four sign combinations,
  INT_MIN as dividend and divisor, INT_MAX, both operand bytes; checks
  quotient and remainder.
- `divmod_unsigned.c`: 37 pairs with bit 15 set on either side, 65535 as
  dividend and divisor, dividend < divisor.
- `divmod_const.c`: 78 checks of `/` and `%` by constants (powers of two,
  -1, 10, INT_MAX, 65535, ...) on negative, INT_MIN and unsigned dividends.
  At -O2 the compiler open-codes most of these, so this case covers the
  compiler's own division sequences as well as the helpers.
- `divmod_sweep.c`: 2,408 helper calls over dividend ranges folded into a
  16-bit checksum, with the host-side reference in the file.

All expected values were computed on the host with Python, not with the
toolchain. Each case was checked to fail on a deliberately wrong entry
(it reports that entry's index) and to reach the helpers at -O2.

`run_divmod_review.py` links the real helpers from `libgcc.a` and calls
them as GCC does:

- every 16-bit dividend x 20 signed divisors
  (`1 -1 2 -2 3 -3 7 -7 10 -10 100 -100 255 256 257 -256 4096 32767 -32767 -32768`)
  through `_divhi3` and `_modhi3`, and x 14 unsigned divisors
  (`1 2 3 7 10 100 255 256 257 4096 32767 32768 32769 65535`) through
  `_udivhi3` and `_umodhi3`: 4,456,448 calls, each checking X, S and
  Y/U/DP canaries;
- every 16-bit dividend with divisor 0 through all four wrappers: 262,144
  calls, each must reach `_abort`;
- `_seuclid` and `_euclid` called directly for 19 signed and 15 unsigned
  edge dividends x the same divisors (590 calls), checking both the stacked
  quotient and the modulus in D. This includes INT_MIN / -1.

A mutated reference (floor instead of truncation) makes the script report
56,311 failures for divisor -7, so it does detect wrong results.

## Results

Observed on macOS ARM64 with the flake's MC6809 0.6.0 emulator, toolchain
built from `043e30e`:

| Check | Result |
|---|---:|
| `tests/run_tests.py divmod` (4 cases x 3 levels) | 12 pass |
| `run_divmod_review.py` sweep (68 helper/divisor pairs x 65,536) | 4,456,448 pass |
| divide by zero -> `_abort` | 262,144 pass |
| `_seuclid`/`_euclid` direct, edge dividends | 590 pass |

The full script takes about 200 s on 8 processes; `--quick` runs 20
helper/divisor pairs (1,310,720 calls) and `--divisors` picks them explicitly.

Limitations: emulator execution, not hardware; the default ABI only (the
`mdret` multilib's `libgcc.a` was not run); the sweep is exhaustive in the
dividend, not in the divisor.

## Reproduce

```sh
nix build --no-write-lock-file .#toolchain
nix build --no-write-lock-file --impure --out-link /tmp/py --expr "
  let f = builtins.getFlake \"$PWD\";
      pkgs = f.inputs.nixpkgs.legacyPackages.aarch64-darwin;
  in pkgs.python3.withPackages (_: [ f.packages.aarch64-darwin.mc6809 ])"
/tmp/py/bin/python3 -B tests/run_tests.py divmod
/tmp/py/bin/python3 -B tests/review/run_divmod_review.py
```
