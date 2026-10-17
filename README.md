# Smartisan OS 2.0 for HTC HD2

**English** | [简体中文](README.zh-CN.md)

An unofficial SD-card port for HTC HD2 / Leo (576 MB RAM, MAGLDR), combining NexusHD2 CM11 / Android 4.4.1 with Smartisan T1 2.0.0 / Android 4.4.2. **Alpha2** adds real-device fixes for Wi-Fi, Bluetooth, camera and sensors, a working GPS framework/HAL path, restored UI animation, and performance tuning for the HD2's limited RAM and SD storage.

**[Download alpha2 ROM and checksum](https://github.com/DCMMC/hd2-smartisan-os/releases/tag/v2.0-hd2-alpha2)** · [Engineering notes](docs/ENGINEERING.md) · [Build notes](docs/BUILD.md) · [XDA post draft](docs/XDA-POST.en.md) · [Sailfish companion project](https://github.com/DCMMC/hd2-sailfish-os)

The launcher and quick controls fit the 480×800 screen, and interaction is substantially smoother. Wi-Fi scanning, Bluetooth, audio, vibration, still-camera capture and the five legacy sensor devices work on the test phone. GPS initializes and starts tracking; an outdoor satellite fix has not yet been tested.

## Real-device screenshots

<img src="screenshots/desktop.png" width="240" alt="Smartisan launcher on HTC HD2"> <img src="screenshots/quick-controls.png" width="240" alt="Adapted quick-settings panel"> <img src="screenshots/camera.png" width="240" alt="Bundled HD2 Camera on HTC HD2">

These are real 480×800 captures from the HTC HD2. The camera preview uses a hardware Surface that Android's old screencap path cannot reliably read, so the third image shows the working camera UI; a 2560×1920 JPEG capture was separately verified. See [screenshot provenance](screenshots/README.md).

## Hardware status

| Feature | Status |
| --- | --- |
| NativeSD boot, Android framework and touch | Working on the test device |
| Launcher and 3-column/12-switch quick controls | Working at 480×800 |
| App open/close animation | Full Smartisan icon face/edge/shadow flip restored in both directions |
| Wi-Fi | Scanning, WPA connection, DHCP, DNS, route and HTTP connectivity working |
| Bluetooth | Adapter reaches ON; standard GATT profiles bind |
| Camera | 640×480 preview and 2560×1920 still capture working through bundled HD2 Camera |
| Audio and vibration | Working, confirmed by the device owner |
| Sensors | Accelerometer, magnetometer/orientation, proximity and light devices working |
| GPS | HAL, position mode and tracking thread working; outdoor fix untested |
| USB debugging | Always-on root ADB, including early boot |
| Calls, mobile data, suspend/resume | Not validated |
| Battery reporting | Legacy protocol/voltage-unit mismatch can show an inaccurate level |

A normal reboot with alpha2 set `sys.boot_completed=1` at about 49 seconds. A first boot after framework replacement can take 2–3 minutes while Dalvik rebuilds its cache.

## Installation

Verify the alpha2 checksum before installing it:

1. Download `hd2-smartisan-2.0-alpha2-SD.zip` and its `.sha256` file, then verify the checksum.
2. Extract the ZIP. Copy the entire `HD2-SM20` directory to the root of the SD card's first FAT32 partition. Allow at least 2.1 GiB; `rootfs.ext4` is a 2 GiB file and fits below FAT32's single-file limit.
3. In MAGLDR, select **Services → BootSettings → AD SD Dir → HD2-SM20**, then **Boot AD SD**.
4. For automatic startup, set **Boot source → Android from SD** and **AlwaysMenu → NO**.

This is an SD image ZIP, not a recovery-flashable ZIP. Do not flash it to NAND. Existing ext4 and WP7 data partitions do not need to be changed. Back up an existing `HD2-SM20/rootfs.ext4` before replacing it.

On the first HD2 Camera launch, allow the camera and location prompts. The original Smartisan Camera was removed because its gralloc buffer request is incompatible with Leo's PMEM path; the ROM includes the NexusHD2 AOSP Camera under the distinct package `org.hd2port.camera2`.

## Debugging

```sh
adb devices
adb shell
adb logcat -d > hd2-logcat.txt
adb pull /dev/hd2-logcat.txt
```

Root ADB starts without an on-screen authorization prompt. Runtime logs rotate in RAM and disappear on reboot; early boot records are written beside the image in `HD2-SM20`.

## Included work

- Legacy Adreno display, Vector/SortedVector, gralloc, Binder PMEM and Android runtime compatibility.
- 480×800 launcher and SystemUI resources, HWUI texture fallback, JIT tuning, reliable 96 MiB zram and a 24 fps/48-frame boot animation.
- Full forward/reverse Smartisan icon flip in a 256×512 atlas with a 220 ms animation timeline; lightweight unlock and ordinary app-window fallbacks remain animated.
- Single-interface `wlan0` control, legacy `SCAN_RESULTS` conversion and removal of unsupported T1-only network variables.
- Standard Bluedroid startup without Smartisan's optional Qualcomm QAdapter service.
- HD2 AOSP camera fallback, legacy GPS lifecycle handling, always-on ADB and RAM-backed runtime logging.

The repository is scoped to the Smartisan port; companion Sailfish files and SD-card repair history are kept out. It contains reproducible patch scripts, manifests, sanitized evidence and engineering notes. Proprietary system binaries are distributed only inside the ROM release archive. This is a binary adaptation rather than a full Smartisan source release; see [NOTICES.md](NOTICES.md) for attribution.
