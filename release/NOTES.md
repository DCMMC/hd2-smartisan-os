# Smartisan OS 2.0 for HTC HD2 — alpha2 NativeSD

Alpha2 brings the port's major legacy-hardware paths into a usable state on the real 576 MB HTC HD2. The launcher and 3-column/12-switch quick controls fit 480×800. Full forward/reverse Smartisan icon flipping is retained in a smaller 256×512 atlas with a 220 ms timeline; the boot animation runs at 24 fps with 48 frames, and post-boot tuning keeps zram, the interactive governor and deadline scheduler active.

ROM ZIP SHA-256: `d57ca77b2d75d331ffa92e1cd0c0ed0c002733cdb854ec97e7ddfa3063f55cf3`

Working in this build:

- Wi-Fi scanning, WPA connection, DHCP, DNS, route and HTTP connectivity
- Bluetooth ON state and standard GATT profiles
- audio and vibration
- bundled HD2 Camera: 640×480 preview and 2560×1920 still capture
- BMA150 accelerometer, AK8973 magnetic/orientation, CM3602 proximity and light sensors
- GPS HAL, position mode and tracking-thread startup
- always-on root ADB

Calls, mobile data, an outdoor GPS satellite fix, video recording, suspend/resume and long-term battery behavior remain unvalidated. Battery percentage can be inaccurate. Smartisan Camera was removed because its buffer allocation is incompatible with Leo PMEM; use the included HD2 Camera and allow its camera/location prompts on first launch.

Extract `hd2-smartisan-2.0-alpha2-SD.zip` and copy the complete `HD2-SM20` folder to the first FAT32 partition. In MAGLDR select **Services → BootSettings → AD SD Dir → HD2-SM20**, then **Boot AD SD**. For automatic startup select **Boot source → Android from SD** and set **AlwaysMenu → NO**. This is an SD image archive, not a recovery-flashable ZIP; do not flash it to NAND.

[English README](https://github.com/DCMMC/hd2-smartisan-os/blob/main/README.md) · [简体中文](https://github.com/DCMMC/hd2-smartisan-os/blob/main/README.zh-CN.md) · [Engineering notes](https://github.com/DCMMC/hd2-smartisan-os/blob/main/docs/ENGINEERING.md)

---

# HTC HD2 Smartisan OS 2.0 — alpha2 NativeSD

alpha2 已在 576 MB HTC HD2 真机打通主要旧硬件路径：桌面与三列 12 开关下拉页适配 480×800，应用打开/关闭时完整保留图标正面、侧面和阴影的双向翻页，使用 256×512 atlas 和 220 ms 时间线；开机动画为 24 fps/48 帧，启动完成后会确保 zram、interactive governor 和 deadline 调度器保持生效。

ROM ZIP SHA-256：`d57ca77b2d75d331ffa92e1cd0c0ed0c002733cdb854ec97e7ddfa3063f55cf3`

本版可用：

- Wi-Fi 扫描、WPA 连接、DHCP、DNS、默认路由和 HTTP 联网
- 蓝牙 ON 状态和标准 GATT profiles
- 声音、振动
- 内置 HD2 相机：640×480 预览与 2560×1920 静态拍照
- BMA150 加速度、AK8973 磁场/方向、CM3602 距离和光线传感器
- GPS HAL、定位模式与跟踪线程启动
- 常开 root ADB

通话、移动数据、室外 GPS 卫星定位、录像、休眠/唤醒及长期耗电仍未验证，电量百分比可能不准。原锤子相机的缓冲区分配与 Leo PMEM 不兼容，所以已移除；请使用包内 HD2 相机，第一次打开时允许相机和位置信息权限。

解压 `hd2-smartisan-2.0-alpha2-SD.zip`，将整个 `HD2-SM20` 放到 SD 第一分区 FAT32 根目录。MAGLDR 中选择 **Services → BootSettings → AD SD Dir → HD2-SM20**，然后 **Boot AD SD**。自动启动请选择 **Boot source → Android from SD**，并把 **AlwaysMenu** 设为 **NO**。这是 SD 镜像压缩包，不是 Recovery 卡刷包，不要刷入 NAND。

<img src="https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/main/screenshots/desktop.png" width="240" alt="HD2 Smartisan desktop"> <img src="https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/main/screenshots/quick-controls.png" width="240" alt="HD2 quick controls"> <img src="https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/main/screenshots/camera.png" width="240" alt="HD2 Camera">
