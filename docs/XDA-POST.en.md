# [ROM][SD][MAGLDR][ALPHA2] Smartisan OS 2.0 for HTC HD2

This is an unofficial SD-card port of Smartisan OS 2.0 for the HTC HD2 / Leo (576 MB RAM), using NexusHD2 CM11 / Android 4.4.1 as the hardware base and Smartisan T1 2.0.0 / Android 4.4.2 as the system donor.

The alpha2 build now boots into a correctly sized 480×800 launcher, has a three-column quick-settings panel, and is substantially smoother than the first build. The following paths were tested on the real phone:

- Wi-Fi scanning and Android's AP list
- Bluetooth adapter ON and standard GATT profiles
- audio and vibration
- AOSP HD2 Camera preview plus 2560×1920 still capture
- accelerometer, magnetic/orientation, proximity and light sensors
- GPS HAL initialization and tracking-thread startup
- always-on root ADB

An outdoor GPS satellite fix, calls, mobile data, video recording, suspend/resume and long-term battery behavior are still untested. Battery percentage can be wrong because of the legacy battery protocol. The original Smartisan Camera is replaced by the compatible HD2 AOSP Camera.

Download: https://github.com/DCMMC/hd2-smartisan-os/releases/tag/v2.0-hd2-alpha2

Code, English/Chinese README, real-device screenshots, sanitized debugging records and engineering notes: https://github.com/DCMMC/hd2-smartisan-os

Verify the SHA-256, extract the ZIP, and copy `HD2-SM20` to the root of the first FAT32 SD partition. In MAGLDR select **Services → BootSettings → AD SD Dir → HD2-SM20**, then **Boot AD SD**. For automatic startup set **Boot source → Android from SD** and **AlwaysMenu → NO**.

The rootfs is a 2 GiB ext4 image file, so allow at least 2.1 GiB free. This is **not a recovery-flashable ZIP** and must not be flashed to NAND. Existing ext4/WP7 partitions do not need to be changed. Back up an existing `rootfs.ext4` before replacing it.

A normal reboot on the test installation reached Android boot completion in about 47 seconds and ended the animation by about 62 seconds. A first boot can take 2–3 minutes while Dalvik caches are generated. On the first HD2 Camera launch, allow its camera and location prompts.

![Smartisan launcher on real HTC HD2](https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/v2.0-hd2-alpha2/screenshots/desktop.png)

![Quick controls on real HTC HD2](https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/v2.0-hd2-alpha2/screenshots/quick-controls.png)

![HD2 Camera UI](https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/v2.0-hd2-alpha2/screenshots/camera.png)

Credits and pinned upstream sources are recorded in the repository. Original authors retain their rights; this is an unofficial binary adaptation.
