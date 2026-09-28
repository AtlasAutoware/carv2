#!/usr/bin/env bash
# Build the ATLAS-DRV-1 VESC firmware and a combined image (firmware + VESC bootloader) for the
# first flash of a blank STM32F405 over SWD.
#
#   firmware/vesc/build.sh            # clones the pinned VESC sources into firmware/vesc/.build/
#   firmware/vesc/build.sh --system   # use the arm-none-eabi-gcc on PATH, skip the pinned toolchain
#
# Output in firmware/vesc/out/:
#   atlas_drv1.bin / .hex    the firmware (0x08000000). VESC Tool uploads the .bin over USB.
#   vesc_bootloader.bin      VESC bootloader, HD60 LED variant (0x080E0000)
#   atlas_drv1_full.hex      both, for one SWD write on a blank chip
#   BUILD_INFO.txt           commits, toolchain, sizes, SHA-256
#
# The firmware is VESC 6.06 (matches the VESC Tool 6.06 on the team laptop). VESC 6.06 is
# built upstream with GCC 7-2018-q2; `make arm_sdk_install` inside the bldc tree downloads it from
# developer.arm.com, and this script does that unless --system is given. Newer GCCs work with the
# extra flags below (tested with Ubuntu's 13.2.1; GCC 14 and later may need more).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$HERE/.build"
OUT="$HERE/out"

BLDC_URL="https://github.com/vedderb/bldc.git"
BLDC_REF="94b305ec124b67b0161f2d3d85c4d5b35e48edc5"    # branch release_6_06, 2026-04-23 (FW 6.06)
BOOT_URL="https://github.com/vedderb/bldc-bootloader.git"
BOOT_REF="2cdb167"                                       # 2022-03-01, prebuilt images in build_all/
BOOT_BIN="build_all/60_o_75_300_o_HD60_o_UAVC_OMEGA_o_75_300_R2_o_60_MK3_o_100_250_o_75_300_R3_o_60_MK4_o_60_MK5_o_HD75.bin"

USE_SYSTEM=0
[ "${1:-}" = "--system" ] && USE_SYSTEM=1

mkdir -p "$WORK" "$OUT"

fetch() {  # url ref dir
    if [ ! -d "$3/.git" ]; then
        git clone --filter=blob:none --no-checkout "$1" "$3"
    fi
    git -C "$3" fetch --quiet origin "$2" 2>/dev/null || git -C "$3" fetch --quiet origin
    git -C "$3" checkout --quiet --force "$2"
}

fetch "$BLDC_URL" "$BLDC_REF" "$WORK/bldc"
fetch "$BOOT_URL" "$BOOT_REF" "$WORK/bldc-bootloader"

BLDC="$WORK/bldc"
mkdir -p "$BLDC/hwconf/atlas"
cp "$HERE/hw_atlas_drv1.c" "$HERE/hw_atlas_drv1.h" "$BLDC/hwconf/atlas/"

cd "$BLDC"
PINNED="$BLDC/tools/gcc-arm-none-eabi-7-2018-q2-update"
if [ "$USE_SYSTEM" = 0 ] && [ ! -d "$PINNED" ]; then
    echo ">> fetching the pinned GCC 7-2018-q2 (make arm_sdk_install)"
    make arm_sdk_install || { echo ">> could not fetch it; falling back to the system compiler"; USE_SYSTEM=1; }
fi

EXTRA=""
if [ "$USE_SYSTEM" = 1 ] || [ ! -d "$PINNED" ]; then
    GCC="arm-none-eabi-gcc"
    command -v "$GCC" >/dev/null || { echo "arm-none-eabi-gcc not found (Arch: pacman -S arm-none-eabi-gcc arm-none-eabi-newlib)"; exit 1; }
    # Debian/Ubuntu's toolchain uses GCC's own stdint.h, so newlib's inttypes.h leaves out PRIx64.
    printf '#include <inttypes.h>\nconst char *s = "%%" PRIx64;\n' > "$WORK/t.c"
    if ! "$GCC" -mcpu=cortex-m4 -mthumb -c "$WORK/t.c" -o "$WORK/t.o" 2>/dev/null; then
        EXTRA="-D__int64_t_defined=1"
    fi
    # GCC 14 turned these warnings into errors; VESC 6.06 predates that.
    MAJOR="$("$GCC" -dumpversion | cut -d. -f1)"
    if [ "$MAJOR" -ge 14 ]; then
        EXTRA="$EXTRA -Wno-error=incompatible-pointer-types -Wno-error=int-conversion -Wno-error=implicit-function-declaration"
    fi
    # bldc's Makefile uses the pinned toolchain if tools/ has it, else arm-none-eabi- on PATH.
    if [ -d "$PINNED" ]; then mv "$PINNED" "$PINNED.off"; fi
fi

rm -rf "$BLDC/build/atlas_drv1"
make fw_atlas_drv1 -j"$(nproc)" ${EXTRA:+USE_COPT="$EXTRA"}
[ -d "$PINNED.off" ] && mv "$PINNED.off" "$PINNED"

ELF="$BLDC/build/atlas_drv1/atlas_drv1.elf"
OBJCOPY="arm-none-eabi-objcopy"
[ -x "$PINNED/bin/arm-none-eabi-objcopy" ] && OBJCOPY="$PINNED/bin/arm-none-eabi-objcopy"

# fw.mk means the .bin to have 0xFF in the gap over the config sectors (1-2), but ChibiOS's own
# rule builds it first without --gap-fill. Make it again: the VESC bootloader writes every byte.
"$OBJCOPY" -O binary --gap-fill 0xFF "$ELF" "$OUT/atlas_drv1.bin"
cp "$BLDC/build/atlas_drv1/atlas_drv1.hex" "$OUT/"
cp "$WORK/bldc-bootloader/$BOOT_BIN" "$OUT/vesc_bootloader.bin"

# One Intel HEX with the firmware at 0x08000000 and the bootloader at 0x080E0000.
"$OBJCOPY" -I binary -O ihex --change-addresses 0x080E0000 "$OUT/vesc_bootloader.bin" "$OUT/vesc_bootloader.hex"
{ grep -v '^:00000001FF' "$OUT/atlas_drv1.hex"; cat "$OUT/vesc_bootloader.hex"; } > "$OUT/atlas_drv1_full.hex"

{
    echo "ATLAS-DRV-1 VESC firmware, built $(date -u +%Y-%m-%dT%H:%MZ)"
    echo "bldc:            $BLDC_URL @ $(git -C "$BLDC" rev-parse HEAD)"
    echo "bootloader:      $BOOT_URL @ $(git -C "$WORK/bldc-bootloader" rev-parse --short HEAD) ($BOOT_BIN)"
    echo "hwconf sources:  firmware/vesc/hw_atlas_drv1.{c,h} @ $(git -C "$HERE" rev-parse --short HEAD 2>/dev/null || echo '?')$(git -C "$HERE" diff --quiet -- . 2>/dev/null || echo ' (with local changes)')"
    if [ -d "$PINNED" ] && [ "$USE_SYSTEM" = 0 ]; then echo "compiler:        $("$PINNED/bin/arm-none-eabi-gcc" --version | head -1)"; else echo "compiler:        $(arm-none-eabi-gcc --version | head -1)"; fi
    echo "extra flags:     ${EXTRA:-none}"
    "${OBJCOPY%objcopy}size" "$ELF" 2>/dev/null || true
    (cd "$OUT" && sha256sum atlas_drv1.bin vesc_bootloader.bin atlas_drv1_full.hex)
} > "$OUT/BUILD_INFO.txt"
cat "$OUT/BUILD_INFO.txt"
