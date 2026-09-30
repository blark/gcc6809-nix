# Bit-helper boundary review

Scope: default 16-bit-int ABI, GCC 4.3.6 m6809 runtime from source revision
`e401b3bc8b7a100218185683e7d36c100ef9d4b6`. Beads workstream B:
`gcc6809-lo0` (shifts), `gcc6809-u3p` (zero bit counts).

## Contracts and test boundaries

- `gcc/config/m6809/libgcc1.s:43–103`: `_ashlhi3`, `_lshrhi3`,
  `_ashrhi3` take the value in D and an unsigned 16-bit count in X, return
  D and preserve X. Their decrement-before-shift loops execute exactly
  the supplied count, without masking it. At counts >=16 the result is
  zero, or the sign fill for arithmetic right shift. We test that private
  assembly behavior directly; it does **not** make C overshifts defined.
- `gcc/libgcc2.c`: the generic double-word shift implementations become
  `___ashlsi3`, `___lshrsi3`, `___ashrsi3` here because a libgcc word is
  16 bits. Test counts **0–31** numerically. Counts >=32 lead to
  out-of-range shifts inside the C implementation; there is no general
  saturation or modulo-count contract to assert. Optional reporting of
  their current behavior is labeled out-of-contract, not a regression
  oracle.
- `libgcc1.s:175–283`: `___clzhi2`/`___ctzhi2` use X for their input and
  result. The 32-bit versions take their input on the stack and return X.
  Nonzero results are ordinary leading/trailing zero counts.

The assembly yields these zero-input results:

| Direct runtime helper | Zero result |
|---|---:|
| `__clzhi2` | 16 |
| `__clzsi2` | 32 |
| `__ctzhi2` | -1 (`0xffff`) |
| `__ctzsi2` | 15 |

These are **implementation characterizations**, not public guarantees for
zero-input GCC builtins. `ctzhi2` computes `15 - clzhi2(x & -x)`; the wide
helper adds 16 when the low word is zero. Thus zero produces -1 and 15,
not assumed width-sized answers. Do not silently “correct” those values
without a separate contract decision. No C test calls a zero-input
`__builtin_clz*` or `__builtin_ctz*`.

## Tests

- `tests/cases/bit_shift16_edges.c` and `bit_shift32_edges.c`: compiled
  noinline variable shifts against constant golden vectors. Left shifts
  are unsigned; signed right shifts test this target's arithmetic-shift
  behavior. Every count is below the operand width. Include zero, sign
  boundaries, mixed bits, all-ones, and byte/word-boundary counts.
- `tests/cases/bit_count_helpers.c`: direct zero calls and nonzero one-hot
  tests through both named helpers and compiler builtins, at both widths.
- `run_bit_helpers.py`: assembles jump probes and links the **actual
  libgcc archive**. The Python integer oracle is independent of target
  arithmetic. The default matrix covers every valid count, one-hot and
  adjacent values, mixed patterns and deterministic random samples;
  16-bit counts also include 16/17/31/32/33/63/255/256/257 and selected
  values at 32767/32768/65535. Each call checks return PC, S, saved Y/U,
  stack/output boundary canaries, and private 16-bit shift X preservation.
  The 32-bit shift ABI uses X as the hidden result pointer and stack
  arguments at entry S+2 (value) and S+6 (count). DP starts at zero.
- `--exhaustive`: all 65,536 inputs for each 16-bit count helper and each
  16-bit shift at counts 0/15/16; also both 32-bit count helpers over all
  low-word-only and high-word-only values. Not every 32-bit value, count,
  register state, or memory access is exhaustively checked.
- `check_sex_opcode.py`: raw opcode `0x1d`, all 65,536 initial D values;
  checks D, N/Z and PC. Independent of generated code and libgcc.

No changes to the shared test runner or compiler are needed.

## Reproduced emulator defect (`gcc6809-877`)

The pinned **MC6809 0.6.0** `instruction_SEX` clears A for nonnegative B,
 but omits setting A to `0xff` for negative B. A trace of the linked
`___ashrsi3` shows D=`0x8080` unchanged after opcode `0x1d`, when it must
be `0xff80`. Consequently correct compiler output appears to return
`0x80ff8000` for arithmetic `0x80000000 >> 16`, rather than `0xffff8000`.
This is an emulator defect, **not evidence for a GCC/libgcc patch**.

Unmodified emulator, unchanged toolchain:

| Check | Result |
|---|---:|
| Original C suite, five optimization levels | 275 pass |
| Original suite plus three new C files | 285 pass, 5 fail |
| Direct helper default matrix | 18,434 pass, 288 fail |
| Raw SEX opcode, all D inputs | 32,896 pass, 32,640 fail |

The five C failures are all `bit_shift32_edges`; the helper failures are
all arithmetic right shifts of negative values at valid counts 16–31.
Tests are deliberately not marked XFAIL: an emulator-only fix follows
in a separate commit. The compiler and target libraries stay unchanged.

## Reproduce

From this checkout, on a supported host with Nix flakes enabled. Build
timeouts must be at least 600 seconds. Do not change `flake.lock`.
The review scripts are separate from the normal C test discovery.

```sh
root="$PWD"
system="$(nix eval --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-bits.XXXXXX)"
ro='--no-write-lock-file --option allow-import-from-derivation false'
nix build $ro --out-link "$work/toolchain" .#toolchain
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
export GCC6809_TOOLCHAIN="$work/toolchain"
export GCC6809_OPT='-O0 -O1 -O2 -O3 -Os'
unset M6809_LIBC M6809_CFLAGS
"$work/python/bin/python3" -B tests/review/check_sex_opcode.py
"$work/python/bin/python3" -B tests/run_tests.py
"$work/python/bin/python3" -B tests/review/run_bit_helpers.py --exhaustive
# Optional, no numeric pass/fail expectations for these invalid counts:
"$work/python/bin/python3" -B tests/review/run_bit_helpers.py --characterize-overshifts
```

The baseline checks above intentionally exit nonzero. These results are
emulator evidence, not physical-hardware validation.
