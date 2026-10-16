# 修复过程与已知问题

冻结日期：2026-10-17。用户最后反馈为“非常好，现在流畅多了”。以下区分运行证据与未验证功能，不把进程存在或 boot_completed 等同于硬件全部可用。

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

## 流畅度

- Dalvik JIT 缓存由 0 改为 1 MiB；独立整数计算探针得到相同结果，解释执行 569 ms、JIT 58 ms。该数据不是整机速度或界面帧率。
- 96 MiB zram 是逻辑容量，实际压缩内存按需占用。
- 关闭桌面翻转/解锁及系统过渡特效；SD/loop 预读从 1024 KiB 降到 128 KiB。
- 默认 UI 设置只写一次，保留用户后续设置。实现见 `configs/smartisan-compat/hd2-runtime` 和平台补丁脚本。

采样曾出现 50%–70% I/O 等待，不能把所有卡顿都归因于动画。用户确认最终操作明显流畅；zram/JIT 的完整冷启动和长时间稳定性仍未充分测试。相关记录：`logs/hd2-jit-probe.txt`、`smartisan-lag-baseline.log`、`hd2-before-perf.txt`、`hd2-after-perf-top.txt`。

## GPS 与相机

旧 GPS 的 cleanup/init 循环触发 librpc 对已释放对象的访问，采用驱动原有的 `GPS1_CLEANUP_ENABLED=0` 避免反复拆卸 RPC 连接。start/stop 保留；真实定位及长期稳定性尚未验证。

相机只适配了 `MemoryBase` 构造函数导入，见 `tools/patch_smartisan_camera.py`。没有证据证明实际预览、拍照或录像可用。

## 留待继续的工作

通话、蜂窝数据、Wi-Fi、音频、相机、GPS、传感器、休眠、耗电和全新镜像冷启动。电量协议及旧电压单位仍不匹配。Qualcomm 私有缓冲结构、Android 4.4.1/4.4.2 的 JNI/Binder 兼容性不能仅靠静态符号扫描保证。

## SD 与 iOS 的共享调试记录

首次大文件传输因 USB 中断留下 FAT 分配错误，已先备份再通过 Recovery 修复并使用压缩传输。旧 MIUI/MIUI23/AND5 的指定 FAT 镜像先校验备份后删除，保留 ext4 系统。

iOS 的 `still wait for device` 排查发现第一分区的 MBR 类型为 0x07，而 XNU HD2 FAT 搜索接受 0x0B/0x0C。实机仅将第 450 字节改为 0x0C，回读证明分区边界和 WP7 数据未改变。实际 iOS 启动结果未确认。此项是该张卡的历史修复，不应在其他卡上盲目重做。证据见 `logs/ios-partition-repair.json`。
