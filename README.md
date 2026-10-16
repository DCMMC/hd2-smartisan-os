# Smartisan OS 2.0 on HTC HD2

HTC HD2 / Leo（576 MB RAM、1024 MB ROM）的非官方 Smartisan OS 2.0 SD 移植。本阶段最终实验版为 **alpha1**，基于 NexusHD2 CM11 / Android 4.4.1 与 Smartisan T1 2.0.0 / Android 4.4.2。

**[下载 ROM ZIP 与校验文件](https://github.com/DCMMC/hd2-smartisan-os/releases/tag/v2.0-hd2-alpha1)** · [修复过程与证据](docs/ENGINEERING.md) · [构建说明](docs/BUILD.md) · [Sailfish 姊妹项目](https://github.com/DCMMC/hd2-sailfish-os)

用户已确认桌面尺寸正确、操作明显流畅。下拉工具页已适配为 480×800，12 个开关排成三列。USB root ADB 默认开启。通话、Wi-Fi、声音、相机、GPS 和休眠尚未完成实机验证；这是当前进度的冻结版本。

## 实机截图

<img src="screenshots/desktop.png" width="240" alt="HTC HD2 Smartisan 桌面"> <img src="screenshots/quick-controls.png" width="240" alt="适配后的下拉工具页">

截图取自本次调试中的真实 HD2 framebuffer，不是效果图。截图中的系统时间及电量不代表准确的时钟或电池状态；电量协议适配仍有问题。截图来源与采集方法见 [screenshots/README.md](screenshots/README.md)。

## 安装

1. 下载 Release 中的 `hd2-smartisan-2.0-alpha1-SD.zip`，核对同名 `.sha256`。
2. 解压，将整个 `HD2-SM20` 目录复制到 SD 卡第一分区 FAT32 根目录，至少留出 2.1 GiB。镜像是 2 GiB ext4 文件，低于 FAT32 单文件上限。
3. MAGLDR → `Services` → `BootSettings` → `AD SD Dir`，选择 `HD2-SM20`，然后 `Boot AD SD`。
4. 自动启动设置：`Boot source` 选择 `Android from SD`，`AlwaysMenu` 设为 `NO`。

这是 **SD 镜像 ZIP**，不是 Recovery 卡刷包。无需格式化、移动现有 ext4/WP7 分区，也不刷 NAND。返回其他系统时，切换 MAGLDR 的 SD 引导目录。首次启动会生成 Dalvik 缓存；没有统一的启动耗时保证。

## 调试

```sh
adb devices
adb shell
adb logcat -d > hd2-logcat.txt
adb pull /dev/hd2-logcat.txt
```

运行日志保存在内存并滚动，重启清空；早期日志在 FAT32 的 `HD2-SM20` 目录。包中包含自动开启、无需界面授权的 root ADB，适合移植调试用途。

## 归档内容

| 路径 | 内容 |
| --- | --- |
| `tools/`、`configs/smartisan-compat/` | 实际使用的构建、二进制/资源修补、兼容层 C/汇编、探针和性能脚本 |
| `logs/` | 已脱敏的启动、GDB/反汇编、性能和修复记录；保留共享工作区的相关历史 |
| `release/` | 补丁清单、功能状态、ROM 及镜像校验和 |
| `reference-sources/`、`sources.lock.json` | 调试参考代码、上游仓库提交和输入固件校验信息 |
| `docs/` | 构建入口、根因/解决方案及历史记录 |

本次 ROM 已包含显示、Vector/gralloc ABI、Runtime、桌面/下拉布局、纹理缓存、JIT、zram、GPS cleanup 和 ADB 补丁。系统二进制在本次发布前已经完成集成；本次归档未追加硬件修改。详细限制以 [BUILD-STATUS.json](release/BUILD-STATUS.json) 为准，较早日志中的 UNTESTED/pending 仅反映当时状态。

这是混合二进制移植，不是完整 Smartisan 源码发行。上游及第三方版权说明见 [NOTICES.md](NOTICES.md)。
