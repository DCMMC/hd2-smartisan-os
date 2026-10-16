#!/usr/bin/env python3
"""Package the assembled SD image with its matching MAGLDR boot files."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'out/sailfish-alpha0/HD2-SF'
image=folder/'rootfs.ext4'
if not image.is_file() or image.stat().st_size!=2048*1024*1024:
    raise SystemExit('Expected the completed 2 GiB Sailfish image')
for name in ['zImage','initrd.gz']:
    shutil.copy2(ROOT/'out/sailfish-bringup/HD2-SF'/name,folder/name)
(folder/'INSTALL-zh.txt').write_text(
    'Sailfish 2.0.1.11 / HTC HD2 SD alpha3：本阶段最终实验版。\n'
    '用户确认显示、点击、滑动、声音和振动正常；Wi-Fi 与相机仍不可用。\n'
    '本包合入启动、systemd、Android HAL、RGBX/gralloc、44100 Hz 音频与振动配置补丁。\n'
    'Wi-Fi WEXT 扫描补丁和相机快门声等待修复已合入，但不代表连接或拍照可用。\n'
    '将整个 HD2-SF 目录放在 SD 第一分区 FAT32 根目录，至少需 2.1 GiB 空间。\n'
    'MAGLDR：Services > BootSettings > AD SD Dir > HD2-SF；然后 Boot AD SD。\n'
    '自动启动：Boot source 设为 Android from SD，AlwaysMenu 设为 NO。\n'
    '这是 SD 镜像包，不是 Recovery 卡刷包，不刷 NAND。目录名不能改。\n'
    '完整桌面、触摸、通话、Wi-Fi、音频、相机与休眠仍以 BUILD-STATUS.json 为准。\n'
    '早期日志在 FAT32 的 HD2-SF/early-boot.log 和 dmesg-early.log；\n'
    '运行日志在内存 /run/hd2-logs，可用 adb pull /run/hd2-logs 提取，重启清空。\n'
    'USB ADB 从 initramfs 自动开启；电脑执行 adb devices、adb shell。\n'
    'ADB 早期可能以 shell 用户运行。另默认开启 USB root 救援终端：\n'
    'RNDIS 成功后电脑设为 192.168.2.14/24，执行 telnet -b 192.168.2.14 192.168.2.15 2323。\n'
    '创建空文件 DIAGNOSTIC_ONLY 可留在 initramfs，镜像挂载成功后位于 /target。\n'
    '创建空文件 SYSTEMD_DEBUG 可开启详细启动日志，正常使用无需创建。\n'
    'USB 模式界面未适配；不可使用 donor 或官方 OTA 更新本地实验镜像。\n'
    '详见 BUILD-STATUS.json、PATCH-MANIFEST.json 和 README.md。\n'
)
names=['zImage','initrd.gz','rootfs.ext4']
(folder/'SHA256SUMS').write_text(''.join(
    hashlib.file_digest((folder/name).open('rb'),'sha256').hexdigest()+'  '+name+'\n'
    for name in names))
output=ROOT/'out/hd2-sailfish-2.0.1.11-alpha3-SD.zip'
temporary=output.with_suffix('.zip.tmp')
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    for path in sorted(folder.iterdir()):z.write(path,'HD2-SF/'+path.name)
    z.write(ROOT/'sources.lock.json','SOURCES.json')
    z.write(ROOT/'README.md','README.md')
    z.write(ROOT/'out/sailfish-native-abi.json','STATIC-DEPENDENCIES.json')
    z.write(ROOT/'logs/sailfish-patch-manifest.json','PATCH-MANIFEST.json')
    for path in sorted((ROOT/'tools').glob('*sailfish*.py')):
        z.write(path,'patch-sources/tools/'+path.name)
    for path in sorted((ROOT/'configs').glob('sailfish-*')):
        z.write(path,'patch-sources/configs/'+path.name)
    for name in ['configure_debug.py','build_kernel.py','firmware.py','patch_vector_abi.py']:
        z.write(ROOT/'tools'/name,'patch-sources/tools/'+name)
    z.write(ROOT/'configs/hd2-unpack.sh','patch-sources/configs/hd2-unpack.sh')
temporary.replace(output)
output.with_suffix('.zip.sha256').write_text(
    hashlib.file_digest(output.open('rb'),'sha256').hexdigest()+'  '+output.name+'\n')
print(output,output.stat().st_size,flush=True)
