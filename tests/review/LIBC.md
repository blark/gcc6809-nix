# Libc conformance group (Workstream C)

Pinned implementation: newlib 1.15.0 `libc.a`, as built by the flake's
`patches/newlib-m6809.patch`. The standard `string.h` and `stdlib.h`
prototypes come from the installed target sysroot. These tests are
**separate from** crt0, libgcc arithmetic, and the already-reviewed
`longjmp` regressions. No libc implementation change was necessary.

## Contracts and coverage

Three compiled C cases under `tests/cases`, each run at
`-O0 -O1 -O2 -O3 -Os`:

- `libc_memory.c`: `memcpy` on separate arrays; `memmove` in both overlap
  directions; `memset` truncation to unsigned char; `memcmp` ordering,
  equality and zero count; all applicable return pointers and untouched
  boundary bytes. No overlapping `memcpy` or invalid region.
- `libc_strings.c`: `strlen`, `strcmp`, `strncmp`, `strchr` on terminated
  arrays, including a NUL in the middle, a zero comparison count,
  negative/positive ordering (never assumes a specific magnitude) and
  unsigned-byte ordering across 0x7f/0x80. All pointers stay valid.
- `libc_strtol.c`: valid decimal/hex/octal/binary/base-36 inputs,
  optional sign and whitespace, full 32-bit `LONG_MIN` and `LONG_MAX`,
  trailing junk and end-pointer offsets, and two no-conversion inputs.
  Newlib 1.15's implementation treats `"0x"` without a digit as no
  conversion, with `endptr` set to `nptr`; this particular case is a
  **pinned non-conformance**: C99 7.20.1.4p4 would consume the leading
  `0` and set `endptr` to `nptr+1`. This deliberately records newlib's
  current behavior, not a portable libc requirement. The C case labels
  it accordingly; a future newlib fix must update that characterization. No overflow, invalid base, locale or errno behavior
  is claimed.

`-Os` generated assembly contains explicit calls to `_memcpy`,
`_memmove`, `_memset`, `_memcmp`, `_strlen`, `_strcmp`, `_strncmp`,
`_strchr` and `_strtol`, so the tests do not merely exercise folded
compiler builtins. Expectations use fixed constants or individually
checked bytes rather than calls to the same function under test.

## Evidence

On the unchanged library, the previous full five-level C suite had
**335 pass** and no libc-specific cases. The new three cases pass **15/15**
across five levels. Deliberately reversing one assertion in each case
returns failure 1 at `-O0`, `-Os` and `-O2` (9/9 mutant runs detected).
These tests add coverage; they do not reproduce a libc implementation bug.
See the combined-branch review record for full suite results after integration.

## Reproduce

From this branch, with Nix flakes enabled, allow >=600 seconds per build:

```sh
ro='--no-write-lock-file --option allow-import-from-derivation false'
nix build $ro .#toolchain --out-link /tmp/gcc6809-libc-toolchain
GCC6809_OPT='-O0 -O1 -O2 -O3 -Os' nix run $ro .#test -- libc_
```

The normal `nix run .#test` wrapper supplies the flake-patched MC6809
emulator. Do not substitute an unpatched PyPI `uv` environment. These
are emulator results, not physical hardware tests; they do not exercise
crt0 startup, locale variants, streams, allocators, or every libc API.
