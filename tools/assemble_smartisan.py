#!/usr/bin/env python3
"""Assemble a first-boot experiment, NOT a verified Smartisan HD2 release."""
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile
from firmware import unpack_cpio, pack_cpio, new_entry
from configure_debug import configure_smartisan_ramdisk

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'work/hd2-base/system'
DONOR = ROOT/'work/smartisan-donor/system'
STAGE = ROOT/'work/smartisan-stage'
BOOT = ROOT/'out/smartisan-alpha0/HD2-SM20'
NATIVE = ['libandroid_runtime.so','libandroid_servers.so','libbinder.so',
          'libgui.so','libsurfaceflinger.so','libui.so','libqdMetaData.so',
          'libandroidfw.so','libinput.so','libinputservice.so']

def props(path):
    result = {}
    for line in path.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value = line.split('=',1)
            result[key.strip()] = value.strip()
    return result

def links(script,allowed):
    for match in re.finditer(r'\bsymlink\((.*?)\);',script,re.S):
        strings = re.findall(r'"([^"\n]*)"',match[1])
        if not strings:
            continue
        target,*destinations = strings
        for dest in destinations:
            relative = PurePosixPath(dest.lstrip('/'))
            if '..' in relative.parts or not any(dest.startswith(p) for p in allowed):
                continue
            path = STAGE.joinpath(*relative.parts)
            if path.is_symlink() or path.is_file():
                path.unlink()
            path.parent.mkdir(parents=True,exist_ok=True)
            path.symlink_to(target)

def main():
    if STAGE.exists():
        raise SystemExit('Stage exists; move it aside before rebuilding: '+str(STAGE))
    if list(DONOR.rglob('*.odex')):
        raise SystemExit('Prepare donor dex files first')
    shutil.copytree(BASE,STAGE/'system',symlinks=True)
    for folder in ['app','priv-app','framework','fonts','media']:
        target = STAGE/'system'/folder
        if target.exists():shutil.rmtree(target)
        shutil.copytree(DONOR/folder,target,symlinks=True)
    shutil.copytree(DONOR/'etc/permissions',STAGE/'system/etc/permissions',dirs_exist_ok=True)
    copied = []
    for path in (DONOR/'lib').glob('*.so'):
        target = STAGE/'system/lib'/path.name
        if path.name in NATIVE or not target.exists():
            shutil.copy2(path,target)
            copied.append(path.name)
    # This executable and its implementation library are kept as a pair.
    for name in ['surfaceflinger','app_process']:
        shutil.copy2(DONOR/'bin'/name,STAGE/'system/bin'/name)
    base_script = (ROOT/'work/base-boot/META-INF/com/google/android/updater-script').read_text()
    links(base_script, ['/system/'])
    links((ROOT/'downloads/smartisan-updater-script').read_text(),['/system/fonts/'])
    # Keep the small HD2 animation while the first-boot graphics path is unknown.
    animation = BASE/'media/bootanimation.zip'
    if animation.exists():shutil.copy2(animation,STAGE/'system/media/bootanimation.zip')
    settings = props(BASE/'build.prop')
    donor_settings = props(DONOR/'build.prop')
    for key,value in donor_settings.items():
        if 'smartisan' in key or key in ['ro.modversion','ro.housing.color'] or key.startswith('ro.config.'):
            settings[key] = value
    settings.update({
        'ro.build.display.id':'Smartisan 2.0.0 HD2 alpha0 UNTESTED',
        'ro.build.version.release':'4.4.2','ro.build.version.sdk':'19',
        'ro.product.model':'HTC HD2','ro.product.device':'leo',
        'ro.product.board':'htcleo','ro.board.platform':'qsd8k',
        'ro.product.locale.language':'zh','ro.product.locale.region':'CN',
        'ro.sf.lcd_density':'240','ro.opengles.version':'131072',
        'ro.config.low_ram':'true','dalvik.vm.heapgrowthlimit':'64m',
        'dalvik.vm.heapsize':'128m','dalvik.vm.heapstartsize':'8m',
        'persist.sys.dalvik.vm.lib':'libdvm.so','debug.sf.disable_hwc':'1',
        'ro.hd2.port.status':'experimental-unverified',
        'persist.sys.usb.config':'adb','persist.sys.root_access':'3',
    })
    # Do not advertise the donor's Snapdragon 801, GLES3, or 512MB Java heap.
    (STAGE/'system/build.prop').write_text('\n'.join(k+'='+v for k,v in settings.items())+'\n')
    (STAGE/'data').mkdir()
    BOOT.mkdir(parents=True,exist_ok=True)
    ramdisk = unpack_cpio((ROOT/'work/base-boot/boot/boot_NativeSD/initrd.gz').read_bytes())
    for entry in ramdisk:
        if entry.name == 'init.rc':
            script = entry.data.decode()
            start = script.index('\t# wait for sdcard')
            end = script.index('\t# cleanup',start)
            mount = '''    # MAGLDR FAT32 image boot. No internal NAND mount.
    wait /dev/block/mmcblk0p1
    wait /dev/block/mmcblk0p1
    wait /dev/block/mmcblk0p1
    wait /dev/block/mmcblk0p1
    mkdir /boot-sd 0755 root root
    mount vfat /dev/block/mmcblk0p1 /boot-sd noatime nodiratime
    mkdir /NativeSD 0755 root root
    exec /bin/busybox sh /hd2-mount.sh
'''
            script = script[:start]+mount+script[end:]
            script += '''
# Persistent first-boot logs, readable from the FAT32 card.
service hd2-port-logcat /system/bin/logcat -v threadtime -f /boot-sd/HD2-SM20/logcat.txt -r 2048 -n 2
    class core
    user root
    group root log

service hd2-port-klog /system/bin/sh /hd2-klog.sh
    class core
    user root
    group root log
    oneshot
'''
            entry.data = script.encode()
        elif entry.name == 'init.environ.rc':
            entry.data = (ROOT/'work/smartisan-boot/init.environ.rc').read_bytes()
    ramdisk.append(new_entry('hd2-klog.sh',b'#!/system/bin/sh\ndmesg > /boot-sd/HD2-SM20/dmesg.txt\ncat /proc/mounts > /boot-sd/HD2-SM20/mounts.txt\n',inode=max(e.fields[0] for e in ramdisk)+1))
    mount_helper = b'''#!/bin/busybox sh
BB=/bin/busybox
exec >>/boot-sd/HD2-SM20/early-boot.log 2>&1
echo 'HD2 Smartisan alpha0 image mount'
$BB uname -a
$BB cat /proc/partitions
fail() {
    echo "Mount failed: $1"
    $BB dmesg > /boot-sd/HD2-SM20/dmesg-mount-failed.txt
    $BB sync
    while :; do $BB sleep 60; done
}
# Android ueventd uses /dev/block; do not depend on BusyBox's /dev/loop scan.
[ -b /dev/block/loop7 ] || $BB mknod /dev/block/loop7 b 7 7
$BB losetup /dev/block/loop7 /boot-sd/HD2-SM20/rootfs.ext4 || fail losetup
$BB mount -t ext4 -o rw,noatime /dev/block/loop7 /NativeSD || fail ext4
$BB mount --bind /NativeSD/system /system || fail system
$BB mount --bind /NativeSD/data /data || fail data
$BB cat /proc/mounts
$BB sync
'''
    ramdisk.append(new_entry('hd2-mount.sh',mount_helper,inode=max(e.fields[0] for e in ramdisk)+1))
    (BOOT/'initrd.gz').write_bytes(pack_cpio(configure_smartisan_ramdisk(ramdisk)))
    shutil.copy2(ROOT/'work/base-boot/boot/zImage',BOOT/'zImage')
    manifest={'status':'EXPERIMENTAL, NO DEVICE BOOT TEST',
              'base':'NexusHD2-KitKat-CM11.0_V4.0 (Android 4.4.1)',
              'donor':'Smartisan T1 2.0.0-2015091200 (Android 4.4.2)',
              'native_framework_libraries':NATIVE,'added_or_replaced_libraries':sorted(copied),
              'unresolved_risks':['Qualcomm private gralloc handle ABI (ION donor versus PMEM HD2)',
                                  'Android 4.4.1/4.4.2 framework/native and Binder protocol differences',
                                  'JNI registration, GPU, touchscreen, RIL, audio, camera untested']}
    (BOOT/'BUILD-STATUS.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Metadata commands are interpreted narrowly by make_ext4.py; never run
    # either donor updater-script on the handset.
    (ROOT/'work/base-permissions.txt').write_text(base_script)
    from integrate_smartisan_compat import integrate
    integrate()
    print('Staged experimental system:',STAGE)
    print('Boot files:',BOOT)

if __name__ == '__main__':main()
