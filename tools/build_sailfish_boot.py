#!/usr/bin/env python3
"""Package the compiled kernel and SD diagnostic initramfs for MAGLDR."""
from pathlib import Path
import hashlib
import shutil
import stat
import zipfile
from firmware import new_entry, pack_cpio, unpack_cpio
from patch_sailfish_adbd import main as patch_adbd

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'out/sailfish-bringup/HD2-SF'
out.mkdir(parents=True,exist_ok=True)
kernel = ROOT / 'out/sailfish-kernel-experimental/zImage'
busybox = ROOT / 'sources/device-leo/ramdisk/bin/busybox'
entries = []
for name in ['bin','sbin','dev','proc','sys','run','sd','ext','target','etc']:
    entries.append(new_entry(name, mode=stat.S_IFDIR|0o755, inode=len(entries)+1))
entries.append(new_entry('bin/busybox',busybox.read_bytes(),inode=len(entries)+1))
entries.append(new_entry('bin/sh',b'busybox',stat.S_IFLNK|0o777,inode=len(entries)+1))
entries.append(new_entry('sbin/sh',b'/bin/busybox',stat.S_IFLNK|0o777,inode=len(entries)+1))
patch_adbd()
adbd=(ROOT/'out/sailfish-debug-tools/hd2-adbd').read_bytes()
entries.append(new_entry('sbin/adbd',adbd,inode=len(entries)+1))
for target,source in [('hd2-unpack.sh','hd2-unpack.sh'),('hd2-usb-setup','sailfish-usb-setup')]:
    entries.append(new_entry(target,(ROOT/'configs'/source).read_bytes(),inode=len(entries)+1))
entries.append(new_entry('init',(ROOT/'configs/sailfish-init').read_bytes(),inode=len(entries)+1))
entries.append(new_entry('etc/hd2-port-id',b'sailfish-hybris-leo-initramfs\n',
                         mode=stat.S_IFREG|0o644,inode=len(entries)+1))
for name,major,minor in [('dev/console',5,1),('dev/null',1,3)]:
    entry = new_entry(name,mode=stat.S_IFCHR|0o600,inode=len(entries)+1)
    entry.fields[9:11] = [major,minor]
    entries.append(entry)
packed = pack_cpio(entries)
assert [(e.name,e.data) for e in unpack_cpio(packed)] == [(e.name,e.data) for e in entries]
(out/'initrd.gz').write_bytes(packed)
shutil.copy2(kernel,out/'zImage')
(out/'STATUS.txt').write_text(
    'EXPERIMENTAL HD2 kernel + SD diagnostic initramfs. NOT a complete Sailfish OS ROM.\n'
    'MAGLDR: Services > BootSettings > AD SD Dir > HD2-SF; then Boot AD SD.\n'
    'A missing rootfs intentionally stops after writing logs to this folder.\n'
    'See the repository README for current status and rootfs prerequisites.\n'
    'USB ADB and a root shell at USB 192.168.2.15:23 start automatically.\n'
    'Early ADB can run as uid 2000; USB telnet provides the root rescue shell.\n'
)
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256((out/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['zImage','initrd.gz']))
with zipfile.ZipFile(ROOT/'out/hd2-sailfish-bringup.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out.iterdir()):
        z.write(p,'HD2-SF/'+p.name)
print(ROOT/'out/hd2-sailfish-bringup.zip')
