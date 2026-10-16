#!/usr/bin/env python3
"""Build a small Recovery update for the already-transferred Smartisan image."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT/'logs/smartisan-compat-manifest.json').read_text())
stage = ROOT/'work/smartisan-runtime-patch'
stage.mkdir(exist_ok=True)
for name in report['files']:
    dest = stage/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/'work/smartisan-stage'/name, dest)
    dest.chmod(0o755 if '/bin/' in name else 0o644)
shutil.copyfile(ROOT/'out/smartisan-alpha0/HD2-SM20/initrd.gz', stage/'initrd.gz')
(stage/'removed-files.txt').write_text('\n'.join(report['removed'])+'\n')
shutil.copyfile(ROOT/'logs/smartisan-compat-manifest.json', stage/'manifest.json')
(stage/'apply-recovery.sh').write_text('''#!/sbin/sh
set -eu
BB=/sbin/busybox
[ -x "$BB" ] || { echo 'Run in Recovery'; exit 1; }
cd "$(dirname "$0")"
BASE=$PWD
SD=${1:-/sdcard}
IMAGE=$SD/HD2-SM20/rootfs.ext4
[ -f "$IMAGE" ] || { echo 'Missing HD2-SM20/rootfs.ext4'; exit 1; }
$BB grep -q ' /NativeSD ' /proc/mounts && { echo 'Smartisan image is running'; exit 1; }
LOOP=/dev/block/loop6
[ -b "$LOOP" ] || $BB mknod "$LOOP" b 7 6
if $BB losetup "$LOOP" >/dev/null 2>&1; then echo 'loop6 busy'; exit 1; fi
$BB mkdir -p /tmp/hd2-sm-patch
$BB losetup "$LOOP" "$IMAGE"
trap '$BB umount /tmp/hd2-sm-patch; $BB losetup -d "$LOOP"' EXIT
$BB mount -t ext4 "$LOOP" /tmp/hd2-sm-patch
$BB cp -a system/. /tmp/hd2-sm-patch/system/
$BB chown -R 0:0 /tmp/hd2-sm-patch/system/lib/libhd2compat.so
$BB chown 0:2000 /tmp/hd2-sm-patch/system/bin/app_process /tmp/hd2-sm-patch/system/bin/app_process.hd2
while IFS= read -r file; do
    case "$file" in system/app/NfcNci.apk|system/app/TimeService.apk|system/app/qcrilmsgtunnel.apk|system/etc/permissions/*nfc*.xml|system/etc/permissions/android.hardware.wifi.direct.xml)
        $BB rm -f "/tmp/hd2-sm-patch/$file";;
    esac
done < removed-files.txt
$BB cp initrd.gz "$SD/HD2-SM20/initrd.gz.new"
$BB sync
$BB mv "$SD/HD2-SM20/initrd.gz.new" "$SD/HD2-SM20/initrd.gz"
$BB sync
echo 'Smartisan runtime compatibility update applied.'
''')
(stage/'apply-recovery.sh').chmod(0o755)
output = ROOT/'out/hd2-smartisan-runtime-patch.tar.gz'
with tarfile.open(output, 'w:gz', compresslevel=1) as packed:
    for path in sorted(stage.rglob('*')):
        if path.is_file():
            info = packed.gettarinfo(str(path), 'smartisan-runtime-patch/'+str(path.relative_to(stage)))
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            with path.open('rb') as content:
                packed.addfile(info, content)
output.with_suffix('.gz.sha256').write_text(hashlib.file_digest(output.open('rb'), 'sha256').hexdigest()+'  '+output.name+'\n')
print(output, output.stat().st_size)
