#!/usr/bin/env python3
"""Build the pinned HD2 kernel with the legacy Sailfish config fragment."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--jobs', type=int, default=min(8, os.cpu_count() or 2))
    ap.add_argument('--cross', default=str(ROOT / 'sources/toolchain-4.4.3/bin/arm-eabi-'))
    args = ap.parse_args()
    src = ROOT / 'sources/kernel-tytung'
    if 'kobject_create_and_add("cgroup", fs_kobj)' not in (src/'kernel/cgroup.c').read_text():
        subprocess.run(['patch','-p1','-i',str(ROOT/'configs/sailfish-cgroup-sysfs.patch')],
                       cwd=src,check=True)
    # accept4 exists in net/socket.c, but this ARM syscall table predates its
    # EABI slot. Journald 208 requires the direct syscall, numbered 366 upstream.
    if 'CALL(sys_accept4)' not in (src/'arch/arm/kernel/calls.S').read_text():
        subprocess.run(['patch','-p1','-i',str(ROOT/'configs/sailfish-arm-accept4.patch')],
                       cwd=src,check=True)
    # ConnMan/wpa_supplicant uses standard WEXT scans. The Android CSCAN
    # option must not reject those requests when its private API is unused.
    wifi = src/'drivers/net/wireless/bcm4329/wl_iw.c'
    if 'HD2 Sailfish: allow standard WEXT scans' not in wifi.read_text():
        subprocess.run(['patch','-p1','-i',str(ROOT/'configs/sailfish-bcm4329-wext-scan.patch')],
                       cwd=src,check=True)
    # Perl >= 5.22 rejects defined(@array); the cached constants array is
    # nonempty exactly when a cached HZ value exists.
    timeconst = src / 'kernel/timeconst.pl'
    original = timeconst.read_text()
    timeconst.write_text(original.replace('defined(@val)', '@val'))
    out = ROOT / 'work/kernel-sailfish'
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.cross + 'gcc', '--version'], check=True)
    make = ['make', '-C', str(src), 'O=' + str(out), 'ARCH=arm',
            'CROSS_COMPILE=' + args.cross, 'HOSTCFLAGS=-O2 -fcommon']
    subprocess.run(make + ['htcleo_defconfig'], check=True)
    fragment = (ROOT / 'configs/sailfish-legacy.fragment').read_text()
    keys = set(re.findall(r'CONFIG_\w+', fragment))
    cfg = (out / '.config').read_text().splitlines()
    cfg = [s for s in cfg if not any(re.match(r'(?:# )?' + k + r'(?:=| )', s) for k in keys)]
    cfg.append(fragment)
    (out / '.config').write_text('\n'.join(cfg) + '\n')
    subprocess.run(make + ['oldconfig'], input='\n' * 1000, text=True, check=True)
    actual = (out / '.config').read_text()
    missing = [s for s in fragment.splitlines() if re.match(r'CONFIG_\w+=', s) and s not in actual.splitlines()]
    if missing:
        raise SystemExit('Kernel cannot satisfy config: ' + ', '.join(missing))
    subprocess.run(make + ['-j' + str(args.jobs), 'zImage', 'modules'], check=True)
    dest = ROOT / 'out/sailfish-kernel-experimental'
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / 'arch/arm/boot/zImage', dest / 'zImage')
    shutil.copy2(out / '.config', dest / 'kernel.config')
    subprocess.run(make + ['INSTALL_MOD_PATH=' + str(dest.resolve()), 'modules_install'], check=True)
    print('Experimental kernel only; no Sailfish HAL/rootfs or hardware test:', dest)

if __name__ == '__main__':
    main()
