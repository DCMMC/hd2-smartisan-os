本阶段最终实验版，适用于 HTC HD2 / Leo + MAGLDR，FAT32 内 2 GiB ext4 镜像启动。系统二进制延续已验证的 alpha1，本次刷新发布说明和完整工程归档。

- 用户确认桌面尺寸正确，操作明显流畅；下拉工具页为三列、12 个开关。
- 包含显示/Vector/gralloc/Runtime 兼容、桌面和 SystemUI 适配、HWUI 纹理回退、JIT/zram、GPS cleanup 和默认 root ADB。
- 通话、数据、Wi-Fi、声音、相机、GPS、休眠及干净镜像首次冷启动未完成验证；电量显示和 GPU 截图路径仍有问题。

下载 `hd2-smartisan-2.0-alpha1-SD.zip`，按同名 `.sha256` 核对，解压后将整个 `HD2-SM20` 放在 SD 第一分区 FAT32 根目录。MAGLDR 的 `AD SD Dir` 选择 `HD2-SM20`，然后 `Boot AD SD`。这不是 Recovery 卡刷包，不刷 NAND。

[安装、调试与源码](https://github.com/DCMMC/hd2-smartisan-os/tree/v2.0-hd2-alpha1) · [问题根因和解决方案](https://github.com/DCMMC/hd2-smartisan-os/blob/v2.0-hd2-alpha1/docs/ENGINEERING.md)

<img src="https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/v2.0-hd2-alpha1/screenshots/desktop.png" width="240" alt="HD2 Smartisan desktop"> <img src="https://raw.githubusercontent.com/DCMMC/hd2-smartisan-os/v2.0-hd2-alpha1/screenshots/quick-controls.png" width="240" alt="HD2 Smartisan quick controls">

截图来自本次调试的真实 framebuffer。代码、补丁、探针、脱敏 debug 记录、来源锁定、校验和和解决方案均在仓库；第三方组件保留原有权利与许可。
