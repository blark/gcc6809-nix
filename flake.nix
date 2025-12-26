{
  description = "GCC 6809 cross-compiler toolchain for macOS ARM64";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  };

  outputs = { self, nixpkgs }:
    let
      # Currently only supports aarch64-darwin due to ARM64-specific patches
      supportedSystems = [ "aarch64-darwin" ];

      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;

      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};

          target = "m6809-unknown-none";

          # Flags to compile GCC 4.3.6 with modern clang/gcc - suppress warnings
          # that are now errors, and use legacy GNU89 inline semantics
          hostCflags = builtins.concatStringsSep " " [
            "-DTARGET_GCC_VERSION=4003"
            "-O2"
            "-fgnu89-inline"
            "-Wno-format-security"
            "-Wno-pedantic"
            "-Wno-implicit-fallthrough"
            "-Wno-format"
            "-Wno-enum-conversion"
            "-Wno-use-after-free"
          ];

          # Cross-compiler for Motorola 6809. Build order is unusual:
          # 1. Build ASxxxx assembler (as6809, aslink)
          # 2. Install assembler so GCC configure can find it
          # 3. Configure and build GCC using the installed assembler
          gcc6809 = pkgs.stdenv.mkDerivation {
            pname = "gcc6809";
            version = "4.3.6";

            src = pkgs.fetchgit {
              url = "https://gitlab.com/dfffffff/gcc6809.git";
              rev = "e401b3bc8b7a100218185683e7d36c100ef9d4b6";
              sha256 = "1h6hwsn8876j3lfww9fg4j3wv20w0dnaf3599pa5vxwv3vzjadhp";
            };

            patches = [ ./patches/arm64-darwin.patch ];

            # gcc12 required because macOS clang can't build GCC
            nativeBuildInputs = with pkgs; [
              gcc12
              gnumake
              texinfo
              flex
              bison
              m4
            ];

            buildInputs = with pkgs; [
              gmp
              mpfr
              libmpc
              zlib
            ];

            # Don't try to strip cross-compiled binaries
            dontStrip = true;

            # Disable fixup for cross-compiler outputs
            dontPatchELF = true;
            dontPatchShebangs = true;

            # WORKAROUND: Nix's updateAutotoolsGnuConfigScriptsPhase replaces config.sub
            # with a modern version that doesn't recognize m6809. This runs AFTER patches
            # are applied but BEFORE preConfigure, so we must patch config.sub here via sed
            # rather than using a patch file (which would be overwritten).
            preConfigure = ''
              sed -i.bak 's/| m6811/| m6809 | m6811/' config.sub
            '';

            configurePhase = ''
              runHook preConfigure

              export CC=gcc CXX=g++ HOST_CFLAGS="${hostCflags}"

              # Build assembler first (required before GCC configure)
              cd build-6809
              make asm AS_HOST=darwin prefix=$out SUDO=
              cd ..

              mkdir -p build-6809/${target}
              cd build-6809/${target}
              ../../configure \
                --enable-languages=c \
                --target=${target} \
                --program-prefix=${target}- \
                --enable-obsolete \
                --disable-threads \
                --disable-nls \
                --disable-libssp \
                --prefix=$out \
                --with-as=$out/bin/${target}-as \
                --with-ld=$out/bin/${target}-ld

              cd ../..

              runHook postConfigure
            '';

            buildPhase = ''
              runHook preBuild

              # Install assembler before building GCC (GCC build invokes it)
              cd build-6809
              make asm-install AS_HOST=darwin prefix=$out as_prefix=$out SUDO=
              make binutils AS_HOST=darwin prefix=$out as_prefix=$out SUDO=
              cd ..

              export PATH="$out/bin:$PATH"  # GCC build needs to find as6809
              cd build-6809/${target}
              make \
                CFLAGS="$HOST_CFLAGS" \
                CFLAGS_FOR_TARGET="-O2 -g" \
                MAKEINFO=true \
                STRICT_WARN=  # MAKEINFO=true skips docs, STRICT_WARN= disables -Werror
              cd ../..

              runHook postBuild
            '';

            installPhase = ''
              runHook preInstall

              export PATH="$out/bin:$PATH"
              cd build-6809/${target}
              make install \
                CFLAGS="${hostCflags}" \
                CFLAGS_FOR_TARGET="-O2 -g" \
                MAKEINFO=true \
                STRICT_WARN=
              cd ../..

              runHook postInstall
            '';

            meta = {
              description = "GCC cross-compiler for Motorola 6809";
              longDescription = ''
                GCC 4.3.6 with patches for the Motorola 6809 8-bit CPU.
                Includes the ASxxxx assembler suite and libgcc runtime.
                Patched to build and run on macOS ARM64 (Apple Silicon).
              '';
              homepage = "https://gitlab.com/dfffffff/gcc6809";
              license = pkgs.lib.licenses.gpl3Plus;
              platforms = [ "aarch64-darwin" ];
              maintainers = [];
            };
          };

          # Newlib C library for m6809 (stdenvNoCC because we provide gcc6809)
          newlib-m6809 = pkgs.stdenvNoCC.mkDerivation {
            pname = "newlib-m6809";
            version = "1.15.0";

            src = pkgs.fetchurl {
              url = "https://sourceware.org/pub/newlib/newlib-1.15.0.tar.gz";
              sha256 = "0ra4kvyifzkk0yb4vag2frdzd8fa6npq2m6xgnjd2nccsc162jf4";
            };

            patches = [ ./patches/newlib-m6809.patch ];

            # gcc12 needed for host tools used during build
            nativeBuildInputs = [ gcc6809 pkgs.gnumake pkgs.gcc12 pkgs.texinfo ];

            # WORKAROUND: See gcc6809 preConfigure
            preConfigure = ''
              sed -i.bak 's/| m6811/| m6809 | m6811/' config.sub
            '';

            # Disable fixups - cross-compiled output shouldn't be patched
            dontStrip = true;
            dontPatchELF = true;
            dontFixup = true;

            configurePhase = ''
              runHook preConfigure

              export PATH="${gcc6809}/bin:$PATH"

              # WORKAROUND: stdenvNoCC inherits CC/CXX from gcc12 in nativeBuildInputs.
              # Must unset so newlib.6809 script uses m6809-unknown-none-gcc for target code.
              unset CC CXX

              substituteInPlace build/newlib.6809 \
                --replace-fail 'prefix=/usr/local' 'prefix=${gcc6809}' \
                --replace-fail 'gcc-4.3.4' 'gcc'

              cd build
              sh newlib.6809 config

              runHook postConfigure
            '';

            buildPhase = ''
              runHook preBuild

              unset CC CXX
              sh newlib.6809 make

              runHook postBuild
            '';

            installPhase = ''
              runHook preInstall

              mkdir -p $out/${target}/lib
              mkdir -p $out/${target}/include
              cp ${target}/newlib/libc/libc.a $out/${target}/lib/
              cp -r ../newlib/libc/include/* $out/${target}/include/

              runHook postInstall
            '';

            meta = {
              description = "Newlib C library for Motorola 6809";
              homepage = "https://sourceware.org/newlib/";
              license = pkgs.lib.licenses.bsd3;
              platforms = [ "aarch64-darwin" ];
            };
          };

          toolchain = pkgs.symlinkJoin {
            name = "gcc6809-toolchain";
            paths = [ gcc6809 newlib-m6809 ];
            meta = gcc6809.meta // {
              description = "Complete GCC 6809 toolchain with C library";
            };
          };

        in {
          inherit gcc6809 newlib-m6809 toolchain;
          default = toolchain;
        });

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};
        in {
          default = pkgs.mkShell {
            packages = [ self.packages.${system}.toolchain ];
            M6809_SYSROOT = "${self.packages.${system}.toolchain}/m6809-unknown-none";
            M6809_CFLAGS = "-I${self.packages.${system}.toolchain}/m6809-unknown-none/include";
            M6809_LIBC = "${self.packages.${system}.toolchain}/m6809-unknown-none/lib/libc.a";
            shellHook = ''
              echo "GCC 6809 toolchain available"
              echo "  Compiler: m6809-unknown-none-gcc \$M6809_CFLAGS"
              echo "  Linker: aslink ... -l \$M6809_LIBC"
            '';
          };
        });
    };
}
