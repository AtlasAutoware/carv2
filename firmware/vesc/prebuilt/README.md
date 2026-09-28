# Prebuilt ATLAS_DRV1 firmware

Built by `firmware/vesc/build.sh --system` from the commit named in `BUILD_INFO.txt`. Not yet
run on a board.

- `atlas_drv1_full.hex`: firmware (0x08000000) + VESC bootloader (0x080E0000). The first flash
  of a blank STM32, over SWD (docs/FLASHING.md, step 1). Needed once so that VESC Tool can
  update the firmware later.
- `atlas_drv1.bin`: the firmware alone, for VESC Tool (Firmware, Custom File).

Rebuild after any change to `hw_atlas_drv1.c` or `.h` and replace these files.
