# 构建与复现说明

仓库保留实际脚本和调试历史。它依赖历史 donor 二进制，不是从公开源码完整编译 Smartisan 的构建系统。工作目录以仓库根目录为基准；`work/`、`downloads/`、`out/` 不纳入 Git。

## 输入和工具

`sources.lock.json` 记录 NexusHD2 V4.0、Smartisan T1 2.0.0、设备树和 ARM GCC 4.4.3 的来源与哈希。下载后先按记录核对，不要替换成名字相近的其他版本。

主机使用 Python 3、`requirements.txt` 中的库、Java、smali/baksmali、binutils、e2fsprogs/debugfs、fakeroot、cpio/gzip/zip 和 adb。历史脚本硬编码了部分工作区文件名；先准备这些目录：

| 路径 | 内容 |
| --- | --- |
| `work/hd2-base/system/` | NexusHD2 ZIP 的 system |
| `work/base-boot/` | NexusHD2 的 boot 与 META-INF，保留 NativeSD initrd |
| `work/base-permissions.txt` | NexusHD2 updater-script 的 set_perm 规则 |
| `work/smartisan-donor/system/` | Smartisan ZIP 的 system |
| `downloads/smartisan-updater-script` | Smartisan 的 META-INF/com/google/android/updater-script |
| `sources/toolchain-4.4.3/` | 锁定提交的 ARM 工具链 |
| `sources/smali-jars/` | smali/baksmali 及 Java 依赖 |

Smartisan donor 的 145 个带 odex 包均保留 classes.dex。`deodex.py` 优先保留原 dex 并移除 odex；不要用 HD2 框架重新反编译 donor。

## 实际入口

```sh
python3 tools/deodex.py work/smartisan-donor/system
python3 tools/assemble_smartisan.py
python3 tools/integrate_smartisan_compat.py
fakeroot -- python3 tools/make_ext4.py work/smartisan-stage \
  out/smartisan-alpha0/HD2-SM20/rootfs.ext4 \
  --permissions work/base-permissions.txt
python3 tools/integrate_smartisan_compat.py --update-image
# Run only after final device validation:
python3 tools/package_smartisan.py
```

装配和镜像脚本拒绝覆盖已有 stage/image；使用独立工作目录或先改名保存旧产物。集成脚本会调用具体的兼容层、框架和资源补丁，输出清单供比对。脚本执行顺序的细节和输入假设以源码为准。

`integrate_smartisan_compat.py` 还会调用 Wi-Fi、蓝牙、Binder/相机和启动动画补丁，并生成独立包名的 HD2 Camera。`hd2-camera.keystore` 是公开的兼容构建密钥，只用于这个非特权相机包，不能作为安全身份。

图标翻页由 `patch_smartisan_launcher.py` 与 `patch_smartisan_bluetooth.py` 配套生成，前者会根据 recipe、donor 和输出 SHA-256 复用已验证 APK，避免仅因 ZIP 时间戳产生不可复现的文件。集成后可用 `logs/smartisan-launcher-patch.json`、`smartisan-bluetooth-framework-patch.json` 和 `smartisan-compat-manifest.json` 核对配方与最终哈希。

`package_smartisan.py` 使用 DEFLATE level 9 生成 alpha2 Release ZIP。发布的 alpha2 由当前镜像重新打包并通过完整 CRC 与 SHA-256 验证；旧的 Wi-Fi v5 之前的 ZIP 已隔离，不能发布。Release ZIP 包含展开的 ext4 镜像，普通安装直接解压复制即可。

## 验证范围

alpha2 镜像已通过 `e2fsck -fn`，并从 ext4 回读清单中的 25 个集成文件逐一核对 SHA-256，同时确认 10 个应删除路径均不存在；发布 ZIP 也通过完整 CRC 测试。`native_abi_report.py` 可用于寻找明显缺库，静态依赖通过不代表硬件可用。实机验证摘要见 `logs/smartisan-alpha2-hardware-validation.json`。

仓库只保留 Smartisan 移植的构建、调试和验证工具。普通用户按 README 复制目录即可，不需要执行分区或 Recovery 维护脚本。
