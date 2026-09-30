# Review proposal: m6809 longjmp zero return

Base: `bc0cbbc`, using GCC source
`e401b3bc8b7a100218185683e7d36c100ef9d4b6` and newlib 1.15.0.

## Scope and status

This fix changes only `longjmp(env, 0)` in the m6809 newlib port. It does
not change GCC or its host-side ARM64 patches.

**Integrated** after independent review: `patches/newlib-longjmp-zero.patch`
is applied by the newlib derivation in `flake.nix`, and the three C cases
now live in `tests/cases/longjmp_*.c`, so `nix run .#test` covers them.
`run_longjmp_review.py` remains for the exhaustive `_longjmp` ABI check.
The rest of this file is the review record; where it says the patch is
"not enabled" or the tests are "outside tests/cases", that describes the
state at review time. To reproduce the baseline failure today, build newlib
with the patch removed and pass it via `--newlib`, then run the same
commands.

## Bug and proposed fix

`patches/newlib-m6809.patch:35325–35343` loads the stack argument into D,
then eventually restores that exact value into X, the default ABI's int
return register. It does not convert zero to one.

[The specified behavior](https://pubs.opengroup.org/onlinepubs/9799919799/functions/longjmp.html)
is to return `val`, except that zero must become one. Returning zero can
make ordinary `if (setjmp(env) == 0)` code re-enter its initial path.

`patches/newlib-longjmp-zero.patch` adds, immediately after `ldd 2,s`:

```asm
        bne longjmp_value_ready
        ldd #1
longjmp_value_ready:
```

`LDD` sets Z from the complete 16-bit value. Thus `0x0100`, `0xff00`, and all
other nonzero arguments remain unchanged. The added instructions do not
change X (the buffer pointer), S, or the saved context. The existing routine
restores CC afterward. The calling convention and jump-buffer layout stay
the same. No compiler changes are needed; applications must relink with the
fixed libc.

These are claims for the reviewer to verify, not substitutes for review.

## Evidence

Three compiled C regressions:

- `longjmp_zero.c`: a global guard prevents an infinite loop if the broken
  implementation returns zero again. Expected result 1; baseline returns 0.
- `longjmp_values.c`: zero, positive/negative values, both argument bytes,
  signed endpoints, and repeated use of one buffer.
- `longjmp_nested.c`: nested stack unwinding, preserved local state, and
  reuse of the outer context with a negative return value.

All invoke `setjmp` as a switch controlling expression. They avoid the
nonstandard `int value = setjmp(env)` invocation context and do not rely on
changed non-volatile automatic locals surviving a jump. No XFAIL markers
hide the failures.

`run_longjmp_review.py --exhaustive` also links the actual `_longjmp` from
libc and executes it for all **65,536 16-bit argument patterns**. It supplies
an already-saved context and checks X, Y, U, S, DP, CC, PC and jump-buffer
boundary canaries. Y, U, DP and CC vary across the inputs. This does not
exhaust all combinations of CPU state; the C tests separately exercise
saving contexts through `setjmp` and compiler returns-twice handling.

Observed on macOS ARM64 using the flake's MC6809 0.6.0 emulator, with the
same baseline compiler for both library variants:

| Configuration | Original 52 cases | New 3 cases | Exhaustive longjmp |
|---|---:|---:|---:|
| Baseline libc | 260 pass | 15 fail | 65,535 pass, 1 fail |
| Candidate libc | 260 pass | 15 pass | 65,536 pass |

C optimization levels: `-O0 -O1 -Os -O2 -O3`.
All three new cases return 0 before the fix and 1 afterward, at every level.
The sole exhaustive baseline failure is val=0: X is 0 rather than 1; all
other checked restored state matches.

Limitations: emulator execution, not physical hardware; default newlib ABI,
not nonstandard calling conventions; finite compiler test suite, not a
proof of the entire compiler. The port's existing TODO for nonstandard
calling conventions is unchanged.

## Reproduce without modifying the flake

Use a clean checkout of this branch on macOS ARM64. Run from the repository
root in bash or another POSIX shell. Allow **at least 600 seconds** per build.
The absolute local flake reference needs `--impure`; inputs remain pinned
and `--no-write-lock-file` prevents lock changes.

```sh
root="$PWD"
work="$(mktemp -d /tmp/gcc6809-longjmp-review.XXXXXX)"
ro='--no-write-lock-file --option allow-import-from-derivation false'

nix build $ro --out-link "$work/base" .#toolchain

nix build $ro --impure --out-link "$work/newlib" --expr "
  let f = builtins.getFlake \"$root\"; in
  f.packages.aarch64-darwin.newlib-m6809.overrideAttrs (old: {
    patches = old.patches ++ [ $root/patches/newlib-longjmp-zero.patch ];
  })"

nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.aarch64-darwin;
  in pkgs.python3.withPackages (_: [ f.packages.aarch64-darwin.mc6809 ])"

export GCC6809_TOOLCHAIN="$work/base"
export GCC6809_OPT='-O0 -O1 -Os -O2 -O3'
unset M6809_LIBC M6809_CFLAGS

# Expected exit 1: 15 C failures and the exhaustive val=0 failure.
"$work/python/bin/python3" -B tests/review/run_longjmp_review.py \
  --include-suite --exhaustive

# Expected exit 0: 275 C passes and 65,536 exhaustive passes.
"$work/python/bin/python3" -B tests/review/run_longjmp_review.py \
  --newlib "$work/newlib" --include-suite --exhaustive
```

The baseline command intentionally exits nonzero; do not chain it to the
candidate command with `&&` or let `set -e` stop the review there.

## Integration proposal, after approval

1. Add `patches/newlib-longjmp-zero.patch` after `newlib-m6809.patch` in the
   newlib derivation's patch list.
2. Move the three `longjmp_*.c` files into `tests/cases` for routine execution
   through `nix run .#test`.
3. Adjust the review runner's discovery if keeping it after that move, so it
   does not lose or duplicate the new cases. Retain the exhaustive ABI check.

Do not combine this library fix with unrelated GCC changes.
