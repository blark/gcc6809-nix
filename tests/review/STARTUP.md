# crt0 startup contract and review

Workstream C startup bead. `patches/newlib-m6809.patch` adds
`libgloss/m6809/crt0.c`, but the current Nix toolchain installs only
`libc.a`, **not crt0.o**. The normal C test runner calls `_main` directly
with a synthetic stack; it cannot verify reset or crt0. The separate
`run_crt0_review.py` extracts the exact 218-line crt0 source from the
pinned patch, compiles it with this checkout's cross-compiler, links a
compiled C `main` and executes the actual reset vector on MC6809.

## Observed simulator contract

- Reset vector points into startup code. `_start` executes `lds #0x1FFE`
  before entering `main`; `main` observes S within the initial stack frame.
- Linker/loader populates `.data`; crt0 contains **no data copying**.
  The test links `.data` at `0x1000` and verifies initialized value
  `0x1234` remains intact. Linking at zero in this emulator corrupts
  initialized data; it is not a supported simulator memory layout.
- crt0 contains comments promising BSS clearing but **no implementation**.
  The probe seeds BSS to `0xa5a5` before reset and verifies that `main`
  still sees `0xa5a5`: this characterizes absence of clearing, not a
  conformance guarantee. Do not infer BSS is initialized at startup.
- Startup enables simulator IRQ/FIRQ (clears CC bits `0x10`/`0x40`), calls
  `main(void)` (no argc/argv), then `_exit(main_return)` continuously
  writes the low byte to simulator register `0xe001`. Test observes 37;
  it does not claim process-exit semantics. Other interrupt vectors and
  IRQ handling are not exercised.

## Reproduce

From this branch using the patched MC6809 Python package (not a separate
`uv` install). Allow >=600 seconds per Nix build; never change flake.lock:

```sh
ro='--no-write-lock-file --option allow-import-from-derivation false'
root="$PWD"
system="$(nix eval $ro --impure --raw --expr builtins.currentSystem)"
work="$(mktemp -d /tmp/gcc6809-crt0.XXXXXX)"
nix build $ro --out-link "$work/toolchain" .#toolchain
nix build $ro --impure --out-link "$work/python" --expr "
  let f = builtins.getFlake \"$root\";
      pkgs = f.inputs.nixpkgs.legacyPackages.$system;
  in pkgs.python3.withPackages (_: [ f.packages.$system.mc6809 ])"
GCC6809_TOOLCHAIN="$work/toolchain" \
  "$work/python/bin/python3" -B tests/review/run_crt0_review.py
```

Baseline: no crt0 test existed and crt0 is not installed in the toolchain.
New test on unchanged startup implementation: reset/stack/data/IRQ/exit
checks pass; deliberate mutations of `lds #0x1FFE` to `#0x3000` and
simulator exit `rc` to `rc+1` are both detected. BSS clearing, data
copying, argc/argv and host exit were **not** implemented as comments
might imply. No startup fix is claimed: changing those behaviors requires
a documented runtime contract and installation/link integration, outside
the test-only scope. Emulator tests are not physical-hardware evidence.
