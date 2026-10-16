#!/usr/bin/env python3
"""Package the patched HD2 SD ROM; no device writes."""
from pathlib import Path
import hashlib
import zipfile

root=Path(__file__).resolve().parents[1]
folder=root/'out/smartisan-alpha0/HD2-SM20'
(folder/'INSTALL-zh.txt').write_text(
    'Smartisan 2.0 HD2 alpha1：用户已确认桌面尺寸正确、操作明显流畅。\n'
    '本 ZIP 内的系统镜像已合入显示、桌面、下拉工具页、JIT、zram、GPS 清理和 ADB 补丁。\n'
    '将整个 HD2-SM20 文件夹放到 SD 第一分区 FAT32 根目录，至少需 2.1 GiB 空间。\n'
    'MAGLDR：Services > BootSettings > AD SD Dir > HD2-SM20；然后 Boot AD SD。\n'
    '这是 SD 镜像包，不是 Recovery 卡刷包。不要刷到 NAND。\n'
    '失败时保留目录内 early-boot.log、dmesg*.txt、mounts.txt。\n'
    '运行日志用 adb logcat 或 adb pull /dev/hd2-logcat.txt 获取，重启后内存日志清空。\n'
    '通话、Wi-Fi、相机、休眠及整包首次冷启动仍待验证，详见 BUILD-STATUS.json。\n'
    'USB root ADB 从早期启动自动开启，无需在界面中确认；电脑执行 adb shell。\n'
    '来源与完整构建说明见工作区 README.md。\n'
)
files=['zImage','initrd.gz','rootfs.ext4']
(folder/'SHA256SUMS').write_text(''.join(hashlib.file_digest((folder/n).open('rb'),'sha256').hexdigest()+'  '+n+'\n' for n in files))
output=root/'out/hd2-smartisan-2.0-alpha1-SD.zip'
temporary=output.with_suffix('.zip.tmp')
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    for path in sorted(folder.iterdir()):
        z.write(path,'HD2-SM20/'+path.name)
    z.write(root/'sources.lock.json','SOURCES.json')
    z.write(root/'README.md','README.md')
    z.write(root/'logs/smartisan-compat-manifest.json','PATCH-MANIFEST.json')
temporary.replace(output)
output.with_suffix('.zip.sha256').write_text(hashlib.file_digest(output.open('rb'),'sha256').hexdigest()+'  '+output.name+'\n')
print(output, output.stat().st_size, flush=True)
