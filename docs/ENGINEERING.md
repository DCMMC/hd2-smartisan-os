# 修复过程与已知问题

更新日期：2026-10-17。以下只把实机执行过的路径标为可用；仅加载模块或出现进程不算硬件验证。脱敏后的最终证据见 `logs/smartisan-alpha2-hardware-validation.json`。

## 启动与原生接口

| 问题 | 已采用的处理 | 代码与证据 |
| --- | --- | --- |
| 旧 Adreno 显示查询接口与新框架不符 | C 兼容层、app_process 包装及动态库调整 | `configs/smartisan-compat/display.c`、`tools/build_smartisan_compat.py`、`logs/smartisan-display-shim-first.log` |
| CM/Smartisan 的 Vector/SortedVector 虚表不一致 | 保留两种调用约定的汇编桥与导入补丁 | `configs/smartisan-compat/vector.S`、`vector_probe.c`、`tools/patch_vector_abi.py`；`logs/smartisan-vector-probe-result.log` |
| Xperia/新 Qualcomm 与 HD2 alloc_device_t 布局不一致 | 校验原始指令后修补 alloc/free 回调偏移 | `tools/patch_gralloc_abi.py`、`logs/smartisan-gralloc-patch.json` |
| Runtime.gcAndTrim() 缺失 | 转调用既有 Runtime.gc()，不模拟额外 native heap trim | `tools/patch_smartisan_core.py`、`logs/smartisan-core-live-test.log` |
| 模拟存储/FUSE 服务缺失 | 添加 FUSE 服务及重启恢复；vold 不再接管承载系统的 FAT32 分区 | `tools/integrate_smartisan_compat.py`、`logs/smartisan-after-storage.log` |
| T1 独有服务持续报错 | 移除不存在的 NFC、TimeService、qcrilmsgtunnel 及相关权限声明 | `logs/smartisan-compat-manifest.json` |

所有二进制补丁均针对锁定的输入。补丁脚本中的预期字节和清单哈希是适用范围，不能直接套用到其他版本固件。

## 画面、桌面和下拉工具页

Launcher 缺少所需的 720p 纹理，改用包内 1080p 资源并重新计算 480×800 的几何尺寸。桌面固定像素和 SystemUI 的 dp/像素布局分别适配，避免只改全局 DPI 造成下拉页混乱。

相关实现为 `tools/patch_smartisan_launcher.py`、`launcher_resources.py`、`patch_smartisan_systemui.py` 和 `android_resources.py`。`logs/smartisan-launcher-patch.json`、`smartisan-systemui-patch.json` 记录具体资源变更；仓库截图保留最终可见效果。

共享纹理 atlas 的 GPU 导入失败，已使用普通 HWUI 纹理缓存，同时保留 GPU 渲染。`tools/patch_smartisan_hwui.py` 处理该路径。普通 screencap 仍有 genlock/GPU 读回错误，可能拿到旧槽位；截图使用真实 framebuffer 和当前 pan 偏移验证。背景截图问题并未完全解决。

应用图标翻页没有被简化成淡入淡出。`patch_smartisan_launcher.py` 把 donor 固定的 384×1024 图标 atlas 缩为 256×512；实机上的正面、侧面、阴影区域总共使用 158×432，因此所有内容仍在 atlas 内，同时明显减少旧 PMEM 路径的分配量。`patch_smartisan_bluetooth.py` 中的 WindowManager 补丁恢复原始正反向矩阵与明暗动画，将时间线调整为 220 ms，并修正 donor 先把浮点秒数转成整数、导致 `getDuration()` 返回 0 的错误。实机日志分别进入 `mIsEnter=true` 与 `mIsEnter=false` 路径；物理返回键测试约 331 ms 后释放触摸，未出现丢帧、ANR 或崩溃。证据见 `logs/smartisan-animation-performance-validation.json` 和 `logs/icon-flip-v10/`。

## 流畅度

- Dalvik JIT 缓存由 0 改为 1 MiB；独立整数计算探针得到相同结果，解释执行 569 ms、JIT 58 ms。该数据不是整机速度或界面帧率。
- 96 MiB zram 是逻辑容量，实际压缩内存按需占用。启动完成后再次检查并启用 zram，避免系统后续初始化将它关闭；`swappiness=80`、`page-cluster=0`。
- 系统窗口、切换和 Animator 动画保持 1.0 倍，桌面解锁与应用图标翻页均开启。针对高成本内容本身减少像素和重复工作，而不是全局关闭动画：应用窗口回退为 95 ms/2% 位移，桌面返回保留轻微缩放，解锁保留 7 帧交错显示。SD/loop 预读从 1024 KiB 降到 128 KiB。
- 启动完成后重新应用 interactive CPU governor 和 deadline SD 调度器，后台缓存进程上限为 8。默认 UI 设置只写一次，保留用户后续调整。实现见 `configs/smartisan-compat/hd2-runtime` 和平台补丁脚本。
- HD2 该内核的 `interactive/min_sample_time` sysfs 写入会卡住调用者。旧运行时脚本因此长期占用约 96% 的唯一 CPU，并且没有执行到 zram 初始化。当前脚本保留内核默认值，补全“已有 disksize、没有 swap 签名”时的 `mkswap` 回退；oneshot 服务现在能退出，zram 已在实机成为活动 swap。
- 开机动画由 48 fps/96 帧调整为 24 fps/48 帧，并使用 stored ZIP，兼顾可见的连续动画和解码负载；最终文件约 0.94 MiB。

早期采样曾出现 50%–70% I/O 等待，不能把所有卡顿都归因于动画。修复 CPU 占用后，同一 Settings 打开路径从 30 个丢帧、1.528 秒改善到日志中无丢帧、1.093 秒；这是单次实机对照，不代表所有应用。一次未触发 dexopt 的正常重启约 49 秒完成系统启动。framework 变化后的首次启动会重新 dexopt，实测约 165 秒，不能拿它代表普通启动。相关实现和记录：`tools/optimize_smartisan_bootanimation.py`、`logs/hd2-jit-probe.txt`、`smartisan-lag-baseline.log`、`hd2-after-perf-top.txt` 和 `logs/icon-flip-v10/open-post-runtime-fix.log`。

## Wi-Fi 与蓝牙

HD2 的旧 wpa_supplicant 使用 `wlan0` 控制 socket。Smartisan 框架原先同时使用全局 socket、P2P 接口和 Android 4.4 的 `BSS RANGE` 输出：前者导致 `EADDRINUSE`，后两者与该 supplicant 不匹配。`configure_debug.py` 删除重复的全局 socket；`patch_smartisan_wifi.py` 把命令和未带接口名的事件固定到 `wlan0`，并将稳定的旧式 `SCAN_RESULTS` 表转换成 Android 4.4 所需的 BSS 键值格式。

扫描修复后仍无法保存网络，最终定位到 `WifiConfigStore` 在标准 `key_mgmt` 和 PSK 之前写入 `trustedAp`、`autoConnect`、`needLogin`、`hiddenTrusted` 等 T1 专用变量。HD2 的旧 supplicant 对这些命令返回 `FAIL`，框架随即删除网络。v5 补丁跳过这些专用 setter，保留标准 Android 网络配置路径。实机最终达到 supplicant `COMPLETED`，并取得 DHCP 地址、网关、DNS、默认路由和成功的 HTTP 请求。

Smartisan Bluetooth 会无条件绑定 T1 的 Qualcomm QAdapter 服务，而 HD2 只有标准 Bluedroid 栈。直接替换 Bluetooth APK 会因平台签名不同失败，替换 donor JNI 又会发生 ABI 崩溃。因此保留原签名 APK、HD2 JNI/HAL，在 `services.jar` 中跳过可选 QAdapter 注册和绑定。实机状态从 10→11→12，bcm4329 rfkill 为 1，标准 GATT profiles 正常绑定。实现见 `tools/patch_smartisan_bluetooth.py`。

## 相机、GPS 与传感器

相机首先恢复 HD2 `libbinder.so` 的 `MemoryHeapPmem`，并把 donor runtime 对 `ProcessState::self2()` 的导入映射到旧平台的 `self()`。这样 HAL 能报告 `Jellybean Camera Hal` 和后置相机，但 Smartisan 相机仍请求约 2.75 MiB、超出 Leo PMEM 映射限制的 gralloc 缓冲区。

最终 ROM 移除 `CameraSmartisan.apk`，把 NexusHD2 AOSP Camera2 克隆为独立包名 `org.hd2port.camera2`。实机验证了 640×480、15 fps 预览、4 个 PMEM 缓冲区，并成功写入 429881 字节的 2560×1920 JPEG。构建脚本和公开兼容签名密钥为 `tools/build_hd2_camera_fallback.py` 与 `configs/smartisan-compat/hd2-camera.keystore`。视频录制未验证；首次启动需在 Smartisan AppOps 对话框允许相机和位置信息。

旧 GPS 的 cleanup/init 循环会让 librpc 访问已释放对象，因此采用驱动已有的 `GPS1_CLEANUP_ENABLED=0`，保留 start/stop。GPSTest 已触发 capabilities（SCHED/MSB/MSA）、`gps_set_position_mode`、`gps_start` 和工作线程；室内没有验证到卫星 fix。

SensorService 枚举到 BMA150 加速度计、AK8973 磁场/方向、CM3602 距离和光线共 5 个硬件 sensor。实机取得了加速度、磁场、距离和光线数值，说明 IRQ/HAL/框架路径均已运行。

## 尚未验证和已知限制

通话、蜂窝数据、室外 GPS fix、录像、休眠/唤醒、长期耗电和稳定性尚未验证。电量协议及旧电压单位仍不匹配。旧 GPU screencap/genlock 路径不能可靠读回相机的 hardware Surface，但这不影响上述 JPEG 拍摄验证。Qualcomm 私有缓冲结构以及 Android 4.4.1/4.4.2 的 JNI/Binder 兼容性只在已执行路径中得到验证。
