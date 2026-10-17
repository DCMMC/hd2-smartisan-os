#!/usr/bin/env python3
"""Package the patched HD2 SD ROM; no device writes."""
from pathlib import Path
import hashlib
import zipfile

root=Path(__file__).resolve().parents[1]
folder=root/'out/smartisan-alpha0/HD2-SM20'
(folder/'INSTALL-zh.txt').write_text(
    'Smartisan 2.0 HD2 alpha2：桌面、下拉工具页和动画已针对 480x800/HD2 优化。\n'
    '本 ZIP 已合入 Wi-Fi 扫描、蓝牙、声音/振动、传感器、GPS HAL、兼容相机及常开 root ADB 补丁。\n'
    '将整个 HD2-SM20 文件夹放到 SD 第一分区 FAT32 根目录，至少需 2.1 GiB 空间。\n'
    'MAGLDR：Services > BootSettings > AD SD Dir > HD2-SM20；然后 Boot AD SD。\n'
    '这是 SD 镜像包，不是 Recovery 卡刷包。不要刷到 NAND。\n'
    '失败时保留目录内 early-boot.log、dmesg*.txt、mounts.txt。\n'
    '运行日志用 adb logcat 或 adb pull /dev/hd2-logcat.txt 获取，重启后内存日志清空。\n'
    '首次启动会生成 Dalvik 缓存，可能需 2-3 分钟；以后实测约 1 分钟进入桌面。\n'
    '相机首次打开时请允许“位置信息”和“相机”权限；通话、移动数据、室外 GPS 定位和休眠仍待验证。\n'
    'USB root ADB 从早期启动自动开启，无需在界面中确认；电脑执行 adb shell。\n'
    '中英文说明、代码与调试记录：https://github.com/DCMMC/hd2-smartisan-os\n'
)
(folder/'INSTALL-en.txt').write_text(
    'Smartisan OS 2.0 for HTC HD2 / Leo - alpha2 NativeSD image.\n'
    'Extract and copy the complete HD2-SM20 directory to the root of the first FAT32 SD partition.\n'
    'Allow at least 2.1 GiB. In MAGLDR select Services > BootSettings > AD SD Dir > HD2-SM20, then Boot AD SD.\n'
    'This is not a recovery-flashable ZIP and must not be flashed to NAND.\n'
    'The first boot can take 2-3 minutes for Dalvik cache generation; normal tested boots take about one minute.\n'
    'On first HD2 Camera launch, allow the camera and location prompts.\n'
    'Calls, mobile data, outdoor GPS fix, video recording and suspend/resume remain unvalidated.\n'
    'Root ADB is always enabled. Runtime log: adb pull /dev/hd2-logcat.txt\n'
    'English/Chinese documentation, code and sanitized debug records: https://github.com/DCMMC/hd2-smartisan-os\n'
)
files=['zImage','initrd.gz','rootfs.ext4']
(folder/'SHA256SUMS').write_text(''.join(hashlib.file_digest((folder/n).open('rb'),'sha256').hexdigest()+'  '+n+'\n' for n in files))
output=root/'out/hd2-smartisan-2.0-alpha2-SD.zip'
temporary=output.with_suffix('.zip.tmp')
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
    for path in sorted(folder.iterdir()):
        z.write(path,'HD2-SM20/'+path.name)
    z.write(root/'sources.lock.json','SOURCES.json')
    z.write(root/'logs/smartisan-compat-manifest.json','PATCH-MANIFEST.json')
temporary.replace(output)
output.with_suffix('.zip.sha256').write_text(hashlib.file_digest(output.open('rb'),'sha256').hexdigest()+'  '+output.name+'\n')
print(output, output.stat().st_size, flush=True)
