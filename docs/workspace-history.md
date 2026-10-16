# HTC HD2：Smartisan 2.0 与 Sailfish SD 移植工作区

归档更新（2026-10-17）：**用户要求停止继续修复并发布本阶段最终实验版。Smartisan 保持 alpha1；Sailfish 更新为 alpha3，用户已确认显示、点击、滑动、声音和振动。Wi-Fi 与相机仍不可用。完整归档与截图发布于 https://github.com/DCMMC/hd2-smartisan-os 和 https://github.com/DCMMC/hd2-sailfish-os。**

此前阶段记录：**Smartisan 2.0 的全部当前补丁已合入 `out/hd2-smartisan-2.0-alpha1-SD.zip`，用户确认桌面尺寸正确、操作明显流畅。Sailfish 已实机进入图形界面，实际帧缓冲显示 480×800 的语言选择页面；USB ADB 和 root 救援终端可连接。启动、systemd、Android HAL 与图形兼容补丁已固化，已确认自动重启后显示欢迎页面。** 两个系统的完整硬件功能仍待验证。

目标设备是 MAGLDR 启动的 HTC HD2 / Leo。所有安装文件放在 SD 卡，提供的引导脚本不刷写 NAND、radio 或 bootloader。

| 包 | FAT32 根目录下的文件夹 | ext4 镜像大小 | 当前验证范围 |
| --- | --- | --- | --- |
| `out/hd2-smartisan-2.0-alpha1-SD.zip` | `HD2-SM20` | 2 GiB | 桌面和下拉工具页显示；用户确认流畅度改善 |
| `out/hd2-sailfish-2.0.1.11-alpha3-SD.zip` | `HD2-SF` | 2 GiB | systemd、Android HAL、USB ADB、语言选择页面 |

两者可放在同一张 SD 卡不同目录内，至少留出 **4.2 GiB 可用空间**。每个镜像均低于 FAT32 的 4 GiB 单文件上限；本轮无需分区或格式化。包旁的 `.sha256` 和目录内的 `SHA256SUMS` 可用于核对文件。

本次设备传输改用 `out/sd-transfer/`：两个根镜像以 `rootfs.ext4.gz` 传输，通过 Recovery ADB 解压后再启动。压缩文件与解压后的镜像共存时需约 5.5 GiB 空间。`recovery-unpack.sh` 可在 Recovery 中运行；若尚未解压，两个实验包的早期启动也提供自动解压后备入口。解压完成前不会使用 `.unpacking` 临时文件。

2026-10-17 写卡记录：已完整备份 FAT32 上的 MIUI、MIUI23、AND5 到 `backups/fat32-before-hd2-ports-20261017/`，仅删除其中七个旧镜像，保留供 ext4 系统启动的小文件。第一次传输在 `HD2-SM20.copying/rootfs.ext4` 中途因 USB 掉线失败。随后进入 4EXT Recovery，修复未完成文件的 FAT 分配错误；35 个孤立簇先备份到电脑再清理，文件系统检查返回 0，并修正 FSInfo 空闲计数。现已用 `tools/recovery_install.py --filesystem-reviewed` 经 Recovery ADB 完成两个压缩包的传输和手机端解压。每个镜像恰为 2 GiB，gzip CRC 检查通过，两个目录的内核、initrd 和配置文件 SHA-256 回读一致；卡上剩余约 2.16 GiB。完成记录保存在 `logs/recovery-install.json`，Smartisan 实机首启及运行时修复记录见下文；Sailfish 首启已进入内核；启动脚本修复记录见 `logs/sailfish-first-boot/`。

IOS6/7 排查发现 FAT32 第一分区在 MBR 中误标记为 `0x07`，而 [XNU HD2 FAT 定位源码](https://github.com/Garysss123/xnu-hd2) 仅接受 `0x0B/0x0C`。现已通过 Recovery 将其改为 `0x0C`，完整扇区回读确认只有 MBR 第 450 字节发生变化；没有移动、缩放或格式化分区。BPB 隐藏扇区数、分区大小与 MBR 一致，两个 HFSX 镜像的主备头部几何尺寸与文件大小匹配。MBR、BPB、启动文件和孤立簇已备份到 `backups/ios-before-multipartition-fix-20261017/`，修复记录在 `logs/ios-partition-repair.json`。**实际 IOS 启动结果尚待确认**；MAGLDR 中 IOS6 使用 `XNU6` 引导目录，IOS7 使用 `IOS7`。

## Smartisan 真机适配进展（2026-10-17）

已修复旧 Adreno 显示查询接口、CM/Smartisan 的 SortedVector 虚表差异、gralloc 分配设备接口偏移、CPU 调度策略和 framebuffer 缓冲数量。双版本 Vector 探针在真机通过。框架使用模拟存储，已增加独立 FUSE 服务及重启恢复；vold 不再管理承载系统镜像的 FAT32 分区。已移除 HD2 不具备的 NFC 服务，以及缺失 T1 依赖而报错的 TimeService、qcrilmsgtunnel。所有改动通过 `tools/integrate_smartisan_compat.py --update-image` 重建到本地 stage、镜像和 ramdisk。

新增 `Runtime.gcAndTrim()` 兼容处理，转调现有 `Runtime.gc()`，真机探针返回 0；不实现锤子额外的 native heap trim。桌面缺少 720p 纹理的问题改为引用包内 1080p 纹理，并将固定像素几何适配为 480×800，用户已确认桌面尺寸正确。相机 `MemoryBase` 构造函数的导入符号已适配，但未验证拍照。共享纹理 atlas 导入失败，已改用 HWUI 普通纹理缓存，保留 GPU 渲染。修改后语言选择页和桌面画面正常。SystemUI 的固定像素尺寸及整页 dp 尺寸已独立适配，framebuffer 确认下拉工具页 12 个开关完整排成 3 列，用户随后确认流畅度明显改善；背景截图的 GPU 读回错误仍未解决。

压缩恢复补丁：`out/hd2-smartisan-runtime-patch.tar.gz`（约 29.3 MiB），已复制到卡上 `HD2-SM20/runtime-patch.tar.gz`。设备上的展开镜像已更新；卡上原 `rootfs.ext4.gz` 仍是首次传输版本。如重新解压旧 gzip，需在 Recovery 解开此补丁并运行其中 `apply-recovery.sh /sdcard`。完整 ZIP/gzip 的更新状态以其生成时间和清单为准。

普通 screencap 的 GPU 读回路径仍有 genlock 错误，可能返回旧 framebuffer 槽；已通过读取实际 framebuffer 及 pan 偏移确认桌面和工具页。不得把旧截图或仅有 `sys.boot_completed=1` 当成所有图形功能正常。

性能调整：启用 1 MiB Dalvik JIT 缓存（原为 0，即禁用 JIT），关闭桌面解锁/翻转与系统过渡特效，96 MiB zram 逻辑容量（实际压缩内存按需使用），SD/loop 预读从 1024 KiB 降至 128 KiB。独立计算探针结果一致，解释执行 569 ms、JIT 58 ms；该数字不是界面帧率或整体提速倍数。活动采样曾出现 50%–70% SD I/O 等待，不能只归因于动画。一次性界面默认值由 `/system/bin/hd2-runtime` 写入，标记为 `/data/local/hd2-ui-defaults-v1`，之后保留用户设置；JIT 与 zram 的完整冷启动仍待验证。旧 GPS 驱动反复 cleanup/init 时触发 librpc 线程访问已释放对象，现使用其原生 `GPS1_CLEANUP_ENABLED=0` 配置避免拆卸 RPC 连接；GPS start/stop 仍保留，真实定位及长期稳定性待验证。

## 先试 Smartisan 2.0

产物：`out/hd2-smartisan-2.0-alpha1-SD.zip`；解压后的目录也已保留在 `out/smartisan-alpha0/HD2-SM20/`。

1. SD 卡第一分区需要是 FAT32，至少有 **2.1 GiB 可用空间**。无需重新分区；本包使用 FAT32 内的 ext4 镜像文件。
2. 将整个 `HD2-SM20` 文件夹复制到 FAT32 根目录。里面的 `rootfs.ext4` 是 2 GiB，不超过 FAT32 单文件上限。目录名不能改。
3. MAGLDR 中选择 `Services → BootSettings → AD SD Dir → HD2-SM20`，返回主菜单选择 `Boot AD SD`。
4. 首次启动需要在卡上生成 Dalvik 缓存。当前没有实机启动用时或成功率数据。如果停在启动画面，先收集日志，不要反复覆盖镜像。
5. 回到原有系统时，在 MAGLDR 里选回原来的 SD 引导目录。

**这不是 Recovery 卡刷包，不能交给 Recovery 安装，也不能刷入 NAND。** 不要运行下载的 T1 原始包内的 updater-script。

启动后会尝试在 FAT32 的 `HD2-SM20` 目录保存：

- `early-boot.log`：镜像挂载过程。
- `dmesg-mount-failed.txt`：挂载失败时的内核日志。
- `dmesg.txt`、`mounts.txt`：Android 启动后的内核信息和挂载表。
- 旧版 `logcat.txt*` 日志保留；新版运行日志改在内存 `/dev/hd2-logcat.txt*` 中滚动保存（每份 256 KiB），可用 ADB 提取，重启后清空，以减少 SD 卡读写。

如果 ADB 能连接，也可以在电脑运行 `adb logcat -d -v threadtime > hd2-logcat.txt`。该实验包沿用 NexusHD2 调试 ramdisk 的 root ADB 设置。若开机完全没有日志，需要记录屏幕最后显示的内容和 MAGLDR 版本。

实现内容：使用 NexusHD2-KitKat-CM11.0 V4.0 的内核、HD2 HAL、Adreno 200 驱动、RIL 和设备配置，合入 T1 Smartisan 2.0.0 的应用、framework、资源及相关原生库。145 个带 odex 的包实际均保留了原始 `classes.dex`，因此保留原 dex 并删除预优化副本。调整至 240 dpi、低内存配置和 128 MiB Dalvik 最大堆。首轮关闭 HWC，保留 GLES 合成路径。

**已知未解决的风险**：T1 图形库使用的 Qualcomm 私有缓冲区结构可能与 HD2 的 PMEM gralloc 不兼容；Android 4.4.1 基底与 4.4.2 donor 之间仍可能有 JNI、Binder、结构体差异。静态符号检查通过并不代表这些运行时接口兼容。桌面尺寸经用户确认，工具页布局经 framebuffer 确认；用户已确认流畅度明显改善；通话、数据、Wi-Fi、音频和相机尚未验证。具体替换库列表见包内 `BUILD-STATUS.json`。

## Sailfish 2.0.1.11 首启实验包

完整补丁包：`out/hd2-sailfish-2.0.1.11-alpha3-SD.zip`；解压目录保留在 `out/sailfish-alpha0/HD2-SF/`（目录名沿用旧名）。已实机显示 480×800 语言选择页面，完整桌面与硬件功能的验证范围见 `BUILD-STATUS.json`。旧 `alpha0-UNTESTED.zip` 未包含本轮修复，不应用于重装。

1. 将整个 `HD2-SF` 文件夹复制到 SD 第一分区 FAT32 根目录，至少需要 **2.1 GiB 空间**。
2. MAGLDR 中选择 `Services → BootSettings → AD SD Dir → HD2-SF`，然后 `Boot AD SD`。**不要用 Recovery 安装或刷入 NAND。**
3. 早期启动会尝试保存 `early-boot.log`、`dmesg-early.log`、`running-config.gz`。进入 systemd 后，前约十分钟每 15 秒在内存 `/run/hd2-logs/` 更新 `journal.log`、`android-logcat.log`、`dmesg-systemd.log`、`failed-units.log`、`input-devices.log` 和 `mounts.log`，可用 `adb pull /run/hd2-logs` 提取。运行日志重启后清空，避免持续写 SD 卡。
4. 如果黑屏或停在启动画面，保留这些日志。没有日志只能说明尚未成功写入 FAT32，不能据此判断一定是哪一个组件失败。

两个实验包均默认开启 USB ADB，电脑使用 `adb devices`、`adb shell`、`adb pull`。Smartisan 使用 root ADB；Sailfish 在 Android 属性服务建立前，ADB 可能以 shell 用户运行。Sailfish 另默认开启 USB root 救援终端：USB RNDIS 成功后，电脑配置 `192.168.2.14/24`，执行 `telnet 192.168.2.15`。无需创建 `DEBUG_USB`。这些配置已写入镜像，两个系统的 USB ADB 均已实机连接。Sailfish 另有独立于 systemd 的 root 救援端口 `2323`，可执行 `telnet -b 192.168.2.14 192.168.2.15 2323`。

电脑可运行 `python3 tools/capture_boot.py --wait 300` 等待系统 ADB 并收集内核、挂载、进程及系统日志到 `logs/phone-boot-*`。该命令默认跳过 Recovery，避免把 Recovery 的 ADB 连接误认为新系统启动成功。

Sailfish 的调试在挂载根镜像前启动；进入 systemd 后由独立服务管理 ADB 和救援终端，失败后自动重启，不依赖图形界面。放入空文件 `DIAGNOSTIC_ONLY` 可留在 initramfs；镜像如挂载成功位于 `/target`。

内核使用 tytung `kitkat` 分支，已启用 devtmpfs、cgroups、autofs4、tmpfs ACL、ext4、loop 等旧版 Sailfish 要求，并关闭 Android paranoid networking 和 Android lowmemorykiller。编译产物和匹配模块保存在 `out/sailfish-kernel-experimental/`。修复了旧内核构建脚本与现代 Perl 的 `defined(@array)` 不兼容问题。

用户空间取自存档中的 Xperia anzu Sailfish 2.0.1.11 alpha4，包含 systemd 208、glibc 2.19、Qt/Sailfish 桌面和 CM11 hybris 修改库。glibc 标记的最低内核版本为 2.6.32；这不保证整个用户空间兼容本内核。Android 驱动、RIL、EGL、PMEM allocator、设备属性改用 NexusHD2 V4.0；模块使用本轮编译版本。没有使用 Xperia 的 msm7x30 HAL 或分区布局。

已修改：systemd 挂载、Android HAL 启动链、`htcleo-touchscreen` 设备匹配、LCD/按键背光路径、HD2 模块加载、设备身份、EGL 驱动名称和日志。显示选择 `EGL_PLATFORM=fbdev` 与 Qt `hwcomposer` 插件，依据基底 HWC 1.0 接口。移除了 donor 的开机刷 Recovery 入口和 Android sysinit，屏蔽 Xperia 电池保存服务、NAND 挂载和 USB 模式管理。

本轮实机修复包括：先挂载 `/proc` 再安装 BusyBox 链接；静态 ADB 的空属性区访问；cgroup sysfs 挂载点、SECUREBITS 与 ARM `accept4` 系统调用入口；systemd 使用旧内核 `tasks` 接口以及移除不支持的 `OOMScoreAdjust`；Android HAL 使用正确的 bionic 库路径；用户会话运行目录；延后 Wi-Fi 模块加载并补上固件参数，实机已出现 `wlan0`。由于旧内核缺少 `tty0/active`，logind 不支持 VT 切换；将自动登录会话改为本地 console，已确认创建活跃的 nemo/seat0 会话。图形修复将 Qt 的 alpha 要求设为 0，使其匹配 HD2 的 RGBX8888 framebuffer，并将 libhybris 的 alloc/free 回调偏移适配为 HD2 ABI；使用两个 framebuffer 缓冲、1.0 倍主题资源和竖屏默认值。补丁源代码、修改偏移与哈希在 ZIP 的 `patch-sources/` 与 `PATCH-MANIFEST.json`。

alpha2 追加修复：进入桌面后，Wayland 客户端申请服务端缓冲时，`libhybris-eglplatformcommon.so` 的另一处分配回调仍使用 Xperia 偏移 68，误调 HD2 的 free 回调并导致 Lipstick SIGSEGV。已根据真机 GDB 栈将偏移改为 64，补丁安装后以 HD2 protocol-A 滑动事件成功从时钟锁屏进入日期与时间设置页，桌面 PID 保持不变。用户已确认画面和点击正常，修复后的手指滑动现已获用户确认。原 alpha1 ZIP 未包含这一处补丁。没有修改 SIM PIN 或设备锁验证。

图形实机证据：`logs/sailfish-first-boot/sailfish-first-frame-1.png`，来自真实 framebuffer 的活动 pan 页面。它证明语言选择页能够渲染，不代表完整桌面、触摸或所有硬件已经可用。

**仍未解决/验证**：Wi-Fi 与相机仍不可用；通话、数据、传感器和休眠未验证。显示、点击、滑动、声音和振动已获用户确认。后续待查；部分 Qualcomm 私有缓冲区及 droidmedia 接口；systemd `tasks` 兼容方案迁移已有多线程进程的行为。内核没有 `CONFIG_FHANDLE`。rootfs 保留 donor 的 RPM 包记录，不能按官方 HD2 适配执行 OTA 升级。Sailfish 的 USB 模式界面暂不可用，使用自动调试入口。

`out/hd2-sailfish-bringup.zip` 仍保留，**它只有内核和诊断 initramfs，没有 rootfs**；正常尝试完整系统应使用上面的 alpha2 包。引导脚本另支持 SD 第二个 ext4 分区中的 `HD2Ports/sailfish/`，但本轮仅制作 FAT32 镜像方案，不需要重新分区。

## 已完成的必要验证

- 两个 Android 输入包及 Sailfish anzu 输入包的 MD5 与来源公布值一致；另记录 SHA-256。
- Sailfish 实验内核和模块实际编译完成。
- HD2 基底内核确认内建 `CONFIG_BLK_DEV_LOOP=y`、`CONFIG_EXT4_FS=y`、`CONFIG_VFAT_FS=y`。
- Smartisan 关键框架库、app_process、SurfaceFlinger、Dalvik、HD2 gralloc/HWC 的静态依赖检查没有发现缺库或强符号缺失。这是宽松的依赖闭包检查，不能证明旧 Android 链接器实际加载成功。
- ext4 镜像通过 `e2fsck -fn`；核对了 `app_process` 的 0:2000 / 0755 权限、shell 符号链接和 `/data` 的 1000:1000 / 0771 权限。
- initramfs 打包解包与 shell 语法检查通过。
- Sailfish 的主要 HAL、EGL、RIL 和 hybris 服务通过宽松的静态依赖闭包检查；ext4 通过 `e2fsck -fn`，核对了 systemd 可执行权限、Android 权限和 nemo 的数字 UID/GID。这不等于运行时或真机验证。
- 已通过 4EXT Recovery 的 root ADB 执行上述 SD 修复；Smartisan 已确认 root ADB、开机完成、桌面与设置界面进程；Sailfish 已确认 systemd、Android HAL、USB ADB 和语言选择页面；其他硬件功能尚待验证。

## 构建入口

源码版本及输入包哈希见 `sources.lock.json`。`downloads/` 保留原始包，`work/` 保留解包和装配结果，`logs/` 保留编译与转换日志。

```sh
cd /home/DCMMC/Projects/hd2-ports
python3 tools/build_kernel.py
python3 tools/build_sailfish_boot.py
python3 tools/native_abi_report.py
python3 tools/sailfish_abi_report.py
```

Smartisan 的 `tools/assemble_smartisan.py` 从已解包并处理 dex 的 donor/base 生成 stage 和 ramdisk，拒绝覆盖已有 stage。制作新的 ext4 文件可用：

```sh
fakeroot -- python3 tools/make_ext4.py work/smartisan-stage out/new-rootfs.ext4 \
  --permissions work/base-permissions.txt
```

这些脚本只生成本地文件，不格式化 SD 卡或写入块设备。ext4 使用明确的旧版特性集合，避免现代 mkfs 默认的 metadata_csum、64bit、orphan_file 等与旧内核不兼容的特性。

Sailfish 的 `tools/extract_rootfs.py` 在提取 tar 时单独保存数字 UID/GID/权限，`tools/assemble_sailfish.py` 生成适配目录。其镜像不能套用纯 Android 的默认权限：

```sh
fakeroot -- python3 tools/make_ext4.py work/sailfish-stage out/new-sailfish.ext4 \
  --metadata work/sailfish-anzu-metadata.json --permissions work/base-permissions.txt \
  --size-mib 2048 --label HD2-SF
python3 tools/package_sailfish.py
```

装配脚本拒绝覆盖已有 stage，镜像生成脚本拒绝覆盖已有文件。`package_sailfish.py` 打包固定的 `out/sailfish-alpha0/HD2-SF/rootfs.ext4`；上面的 `new-sailfish.ext4` 是另存示例，重新打包前需自行选择目标文件。

## 来源

- [tytung HD2 内核，kitkat 分支](https://github.com/tytung/android_kernel_htcleo-2.6.32/tree/kitkat)
- [NexusHD2 V4.0，作者 tytung](https://androidfilehost.com/?fid=23269279319197173)
- [Smartisan T1 历史固件存档](https://archive.org/details/sdfsfo_202609)，选用 `2.0.0-2015091200-user-sfo.zip`
- [HD2 设备树及静态 BusyBox](https://github.com/MarkDownUnder/android_device_htc_leo/tree/cm-11.0)，仅使用其 BusyBox 制作 Sailfish 诊断包，未混用其 ION 设备配置
- [hybris 早期引导源码](https://github.com/mer-hybris/hybris-boot/tree/hybris-10.1)
- [Sailfish 官方硬件适配说明](https://hadk.sailfishos.org/modifications/)
- [旧 Sailfish 镜像存档](https://archive.org/details/oldsailfishosimages)，选用 `sailfishimages.ruecker.fi/sfa/anzu/alpha4/sailfishos-anzu-release-2.0.1.11-alpha4.zip`
- [Xperia 2011 Sailfish 配置源码](https://github.com/mlehtima/droid-config-2011xperia)
- [Xperia 2011 hybris 设备构建配置](https://github.com/mlehtima/droid-hal-2011xperia)
- [Qt hwcomposer 插件源码](https://github.com/mer-hybris/qt5-qpa-hwcomposer-plugin)

上游源码、固件和二进制保留各自作者版权与许可。本工作区产物尚未公开发布。


## alpha3 硬件修复与归档冻结

44100 Hz 音频、ngfd 的 droid-vibrator 资源映射、bcm4329 标准 WEXT 扫描入口和相机快门声等待修复已由 `tools/finalize_sailfish_release.py` 写入本地 ext4 镜像并回读校验。用户确认声音与振动；Wi-Fi 扫描曾枚举到网络，但用户报告仍无法使用，不能视为 Wi-Fi 已修复。相机绕过 AudioFlinger 等待后仍在预览缓冲分配处失败，记录见 `logs/sailfish-first-boot/minimedia-audio-wait-gdb.txt`。临时 `debug.composition.type=gpu` 实验未合入发布包。当前进度按用户要求冻结，不再继续硬件修复。
