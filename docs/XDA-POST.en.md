# [ROM][SD][MAGLDR][ALPHA] Smartisan OS 2.0 for HTC HD2

I have been working on an unofficial SD port of Smartisan OS 2.0 for the HTC HD2 / Leo. The test device has 576 MB RAM and 1024 MB ROM. This is the current experimental snapshot; hardware support is incomplete.

The launcher fits 480×800, the quick-settings panel has 12 controls in three columns, and interaction is substantially smoother. Calls, data, Wi-Fi, audio, camera, GPS and suspend are not fully tested. Battery reporting and GPU screenshot/readback have known issues.

Download: https://github.com/DCMMC/hd2-smartisan-os/releases/tag/v2.0-hd2-alpha1

Code, English/Chinese README, real-device screenshots, debugging logs and engineering notes: https://github.com/DCMMC/hd2-smartisan-os

Verify the SHA-256, extract the ROM ZIP and copy `HD2-SM20` to the root of the first FAT32 SD partition. In MAGLDR, select Services → BootSettings → AD SD Dir → HD2-SM20, then Boot AD SD. The rootfs is a 2 GiB ext4 image file; allow at least 2.1 GiB free space. This is **not a recovery-flashable ZIP** and must not be flashed to NAND. No repartitioning is required. Back up an existing image before replacing it.

ADB is enabled automatically. The patches were tested incrementally on the running phone; the final clean image has not had a separate cold-boot validation cycle. Full limitations and debugging access are documented in the repository.

![Real HTC HD2 screenshot](https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/main/screenshots/desktop.png)

![Real HTC HD2 screenshot](https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/main/screenshots/quick-controls.png)

Credits and pinned upstream sources are recorded in the repository. Original authors retain their rights; this is an unofficial adaptation.
