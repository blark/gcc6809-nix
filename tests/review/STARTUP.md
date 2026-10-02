# Installed GCC crt0 startup review

This review exercises the **installed**
`lib/gcc/m6809-unknown-none/4.3.6/crt0.o`, built from
`gcc/config/m6809/crt0.S` with `TARGET_UNKNOWN`. The real GCC driver links
this object automatically. The separately present
`libgloss/m6809/crt0.c` in `patches/newlib-m6809.patch` is **not installed**;
it is not the toolchain's startup path. The original source-only probe was
rejected in review and replaced.

`run_crt0_review.py` invokes the normal cross-compiler driver on a C probe,
with `-L$toolchain/m6809-unknown-none/lib` to work around the separately
filed pre-existing `libc.a` search-path bug. `-Wl,--args` lets the probe
supply nonzero `__argc` and `__argv` symbols. It does not manually supply a
startup object or change the entry point. The driver generates the S19
image; its map identifies `__start`, `_main`, `__exit` and the probe
variables, while the S9 record supplies the entry address.

The test first fills **all 64 KiB RAM** with `0xa5` and loads only S19
records. It reads `s_.bss` and `l_.bss` from the driver's link map. Before
startup, every byte in the entire `.bss` extent must still be `0xa5`, while
`.data` contains its initialized value. At the return from startup's
`_memset`, before `atexit` or constructors can legitimately change BSS,
**every byte** must be zero. The byte preceding BSS is unchanged and the
following `.noinit` word still holds the saved loader stack. It then runs
through `main` and the actual exit path.

## Checks on the shipped `TARGET_UNKNOWN` startup

- S9 entry equals linked `__start`; startup saves the loader stack.
  `main` observes S within 16 bytes of each of two distinct loader frames
  (`0xeffe` and `0xdffe`), and `__exit` restores each supplied stack before
  returning to the loader.
- The entire `.bss` extent (28 bytes in the tested link) is zeroed by
  crt0 even though the loader left it nonzero. The initialized `.data`
  value remains `0x1234`. The loader already populated `.data`: this
  layout does not need a ROM-to-RAM copy.
- A constructor executes before `main`. `main` observes that the
  destructor has **not** run; a user `atexit` callback also observes no
  destructor, then the destructor runs before control returns to the
  loader. This checks callback order rather than only their final values.
- `main(int argc, char **argv)` receives the probe-supplied nonzero
  `__argc` and `__argv` symbols: `argc == 2`, `argv[0] == "one"`,
  `argv[1] == "two"`, and `argv[2] == NULL`. This does not claim that a
  bare driver link provides meaningful default arguments: without
  `--args` it defines both linker symbols at address zero.
- `main` returns 37; after `exit` callbacks, installed `__exit` returns
  37 in X/D and restores the loader stack. This is `TARGET_UNKNOWN`, not
  the simulator-specific memory-mapped exit variant. Wrong returned values
  are reported explicitly rather than as a timeout.

The standalone `tests/run_tests.py` flow does **not** link crt0; it calls
`_main` directly with its own stack and initially zero RAM. Its BSS tests
cannot establish whether startup clears RAM. No IRQ or hardware startup
semantics are asserted here. Emulator behavior is not hardware evidence.

## Reproduce

Use the patched emulator packaged by this flake, not an unpatched PyPI
installation. Allow >=600 seconds for each build and leave flake.lock
unchanged:

```sh
root="$PWD"
ro='--no-write-lock-file --option allow-import-from-derivation false'
system="$(nix eval $ro --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-startup.XXXXXX)"
nix build $ro .#toolchain --out-link "$work/toolchain"
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
GCC6809_TOOLCHAIN="$work/toolchain" \
  "$work/python/bin/python3" -B tests/review/run_crt0_review.py
```

Expected: `installed crt0 PASS`, with BSS cleared and exit=37. Baseline
had no test of the installed startup; its false libgloss-source probe
reported BSS left unchanged by code not included in the toolchain. The
reworked probe now checks the actual driver path. Five temporary C-probe
mutations were rejected: returning 38 reports an explicit X/D exit mismatch;
altering the constructor, destructor or forwarded argc reports its own
field; treating BSS as nonzero makes `main` return 80 instead of 37. An
in-memory mutation shortening the real crt0 `_memset` count by one byte is
now detected as an incomplete full-BSS clear; simulating a destructor
before `main` is also detected. Two loader stack initializations ensure
stack restoration is not validated only against one hardcoded final SP.
None of the mutations was committed. No startup implementation patch is
claimed.
