#!/usr/bin/env python3
"""Assemble an unverified HD2/CM11 adaptation of archived Sailfish 2.0.1.11."""
import json
from pathlib import Path
import re
import shutil
from configure_debug import configure_sailfish
from patch_sailfish_systemd import main as patch_systemd
from configure_sailfish_legacy import configure_legacy
from configure_sailfish_hardware import configure_hardware
from patch_sailfish_qpa import main as patch_qpa, RELATIVE as QPA_PATH
from patch_sailfish_gralloc import main as patch_gralloc, PATCHES as GRALLOC_PATHS

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT/'work/sailfish-anzu-rootfs'
BASE = ROOT/'work/hd2-base/system'
STAGE = ROOT/'work/sailfish-stage'
HYBRIS = Path('usr/libexec/droid-hybris/system')

def remove(name):
    p=STAGE/name
    if p.is_symlink() or p.is_file():p.unlink()
    elif p.is_dir():shutil.rmtree(p)

def write(name,text,mode=0o644):
    p=STAGE/name
    if p.is_symlink():p.unlink()
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(mode)

def link(name,target):
    remove(name)
    p=STAGE/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.symlink_to(target)

def unit(name,body,target=None):
    write('etc/systemd/system/'+name,body)
    if target:link('etc/systemd/system/'+target+'.wants/'+name,'../'+name)

def main():
    if STAGE.exists():raise SystemExit('Move existing stage aside before rebuilding')
    shutil.copytree(DONOR,STAGE,symlinks=True)
    for name in ['boot','lib/modules','init-debug','init.semc.rc','init.semc.usb.rc',
                 'init.board.rc','init.device.rc','ueventd.semc.rc','sbin/preinit',
                 'sbin/pre-recovery.sh','usr/share/ssu/board-mappings.d/05-semc-anzu.ini',
                 'var/lib/environment/compositor/droid-hal-device-anzu.conf']:
        remove(name)
    (STAGE/'boot').mkdir()
    shutil.copytree(BASE,STAGE/'system',symlinks=True)
    # Sailfish runs the native Qt desktop; these Android application files are unused.
    for folder in ['app','priv-app','framework','media','etc/init.d','lib/modules']:
        remove('system/'+folder)
    # Never inherit a recovery installer or an Android init.d startup hook.
    for name in ['system/etc/install-recovery.sh','system/etc/install-cm-recovery.sh',
                 'system/bin/sysinit','system/recovery-from-boot.p']:
        remove(name)
    script=(ROOT/'work/base-boot/META-INF/com/google/android/updater-script').read_text()
    for match in re.finditer(r'\bsymlink\((.*?)\);',script,re.S):
        args=re.findall(r'"([^"\n]*)"',match[1])
        if not args:continue
        target,*names=args
        for name in names:
            if name.startswith('/system/bin/') or name.startswith('/system/xbin/'):
                link(name.lstrip('/'),target)

    # Keep the donor's patched bionic/logging and generic Android compatibility
    # libraries. Its msm7x30 HAL and Qualcomm allocator are NOT the HD2's PMEM ABI.
    remove(str(HYBRIS/'lib/hw'))
    link(str(HYBRIS/'lib/hw'),'/system/lib/hw')
    shutil.copy2(BASE/'lib/egl/egl.cfg',STAGE/HYBRIS/'lib/egl/egl.cfg')
    platform_libs=['libmemalloc.so','libqdutils.so','libqservice.so','liboverlay.so',
                   'libexternal.so','libvirtual.so','libgenlock.so']
    replaced=[]
    for name in platform_libs:
        if (BASE/'lib'/name).is_file():
            shutil.copy2(BASE/'lib'/name,STAGE/HYBRIS/'lib'/name)
            replaced.append(name)
        else:remove(str(HYBRIS/'lib'/name))
    # Remove flashing executables from the adaptation directory.
    for name in ['updater','recovery']:remove(str(HYBRIS/'bin'/name))
    shutil.copytree(ROOT/'out/sailfish-kernel-experimental/lib/modules',STAGE/'lib/modules',
                    symlinks=True,ignore=shutil.ignore_patterns('build','source'))
    (STAGE/'system/lib/modules').mkdir()
    for p in (STAGE/'lib/modules').rglob('*.ko'):
        link('system/lib/modules/'+p.name,'/'+str(p.relative_to(STAGE)))
    write('etc/modules-load.d/hd2.conf','bcm4329\nmsm_rmnet\nfuse\n')
    for name in ['data','cache','run','sdcard','vendor']:
        if name not in ['sdcard','vendor']:(STAGE/name).mkdir(exist_ok=True)
    link('sdcard','/run/hd2-sd')
    link('vendor','/system/vendor')
    write('etc/fstab','# Root is the SD image mounted by the HD2 initramfs.\n'
          'devpts /dev/pts devpts gid=5,mode=620 0 0\n'
          'tmpfs /dev/shm tmpfs mode=1777,nosuid,nodev 0 0\n')
    # /system and /data are directories inside this same SD image.
    for name in ['system.mount','sdcard.mount','android-links.service',
                 'droid-battery-monitor.service','usb-moded.service','usb-rescue-mode-off.service']:
        link('etc/systemd/system/'+name,'/dev/null')
    write('etc/hd2-port-id','sailfish-hybris-leo\n')
    write('etc/hw-release','NAME="HTC HD2"\nID=leo\nMER_HA_DEVICE=leo\n'
          'MER_HA_VENDOR=htc\nVERSION_ID=alpha0\nPRETTY_NAME="HTC HD2 SD alpha0 UNTESTED"\n')
    write('usr/share/ssu/board-mappings.d/05-htc-leo.ini',
          '[hwrelease.device]\nleo=leo\n\n[leo]\nprettyModel=HTC HD2\n'
          'deviceManufacturer=HTC\ndeviceDesignation=leo\nimg-arch=armv7hl\nimg-type=fs\n')
    write('default.prop','ro.hardware=htcleo\nro.secure=1\nro.debuggable=1\n'
          'ro.allow.mock.location=0\npersist.sys.usb.config=none\n')
    with (STAGE/'system/build.prop').open('a') as f:
        f.write('\nro.hd2.port.status=experimental-unverified\n')

    # Start Android only as Sailfish's HAL service. No zygote or SurfaceFlinger.
    text=(DONOR/'init.rc').read_text().replace('import /init.${ro.hardware}.rc',
                                             'import /init.htcleo.rc')
    # These Android-only services are not used by Sailfish; removing their blocks
    # also removes every recovery flashing trigger inherited from the donor.
    blocks=re.split(r'(?m)(?=^(?:on |service ))',text)
    remove_services={'flash_recovery','installd','drm','zygote','surfaceflinger',
                     'bootanim','media','miniaf','healthd-charger','adbd'}
    kept=[]
    for block in blocks:
        first=block.splitlines()[0] if block else ''
        if first.startswith('service ') and first.split()[1] in remove_services:continue
        if first=='on property:persist.sys.recovery_update=true':continue
        lines=[line for line in block.splitlines()
               if not re.match(r'\s*(onrestart restart|start|stop) (zygote|media|surfaceflinger|miniaf|adbd)\s*$',line)]
        kept.append('\n'.join(lines)+'\n')
    write('init.rc',''.join(kept))
    write('init.cm.rc','# Android sysinit/superuser services are not used by Sailfish.\n')
    write('init.superuser.rc','# Deliberately empty.\n')
    hd2=(ROOT/'work/base-ramdisk/init.htcleo.rc').read_text()
    hd2=hd2[hd2.index('on boot'):]
    hd2=hd2[:hd2.index('# sdcard daemon')]
    hd2='\n'.join(line for line in hd2.splitlines()
                   if not any(s in line for s in ['mount debugfs','/sys/block/mtdblock','/etc/bluez']))+'\n'
    write('init.htcleo.rc',hd2)
    # Startup supplies hybris libs to Android processes, and leaves glibc's
    # default search path untouched for native Sailfish services.
    startup=(DONOR/'usr/bin/droid/droid-hal-startup.sh').read_text()
    startup=startup.replace('sh /usr/libexec/droid/android-permission-fixup.sh &> /dev/null',
                            'mkdir -p /run/droid-hal /dev/socket')
    startup=startup.replace(':/system/lib',':/system/lib:/system/lib/egl')
    write('usr/bin/droid/droid-hal-startup.sh',startup,0o755)
    write('var/lib/environment/nemo/99-hybris.conf',
          'HYBRIS_LD_LIBRARY_PATH=/usr/libexec/droid-hybris/system/lib:/vendor/lib:/system/lib:/system/lib/egl\n')
    fix=(DONOR/'usr/bin/droid/droid-init-done.sh').read_text().replace(' == ',' = ').replace('let n=$n+1','n=$((n + 1))')
    write('usr/bin/droid/droid-init-done.sh',fix,0o755)

    # Generate udev permissions from the actual HD2 ramdisk, not Xperia rules.
    uid={line.split(':')[0]:line.split(':')[2] for line in (DONOR/'etc/passwd').read_text().splitlines() if ':' in line}
    gid={line.split(':')[0]:line.split(':')[2] for line in (DONOR/'etc/group').read_text().splitlines() if ':' in line}
    rules=['# Generated from NexusHD2 V4.0 ueventd.rc and ueventd.htcleo.rc.']
    for name in ['ueventd.rc','ueventd.htcleo.rc']:
        for line in (ROOT/'work/base-ramdisk'/name).read_text().splitlines():
            fields=line.split()
            if len(fields)!=4 or not fields[0].startswith('/dev/'):continue
            path,mode,owner,group=fields
            if owner not in uid or group not in gid:raise ValueError('Unknown Android identity: '+line)
            if path.startswith('/dev/log/'):
                match='SYMLINK=="alog/*"'
            elif path.rsplit('/',1)[-1]=='*':
                match='SUBSYSTEM=="'+{'/dev/input/*':'input','/dev/graphics/*':'graphics',
                      '/dev/msm_camera/*':'msm_camera','/dev/snd/*':'sound',
                      '/dev/oncrpc/*':'oncrpc','/dev/dri/*':'drm'}.get(path,path.split('/')[2])+'"'
            else:match='KERNEL=="'+path.rsplit('/',1)[-1]+'"'
            rules.append(match+', MODE="'+mode+'", OWNER="'+uid[owner]+'", GROUP="'+gid[group]+'"')
    write('lib/udev/rules.d/999-android-system.rules','\n'.join(rules)+'\n')
    write('lib/udev/rules.d/51-udev-touchscreen.rules',
          'ACTION=="add", SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="htcleo-touchscreen", '
          'SYMLINK+="touchscreen", MODE="0660", GROUP="input", ENV{ID_INPUT_TOUCHSCREEN}="1"\n')
    # NexusHD2 HWC open writes device version 0x01000001 (HWC 1.0/header 1).
    # QPA's v1.0 backend uses a NULL native window and the fbdev EGL platform.
    # The archived donor includes this backend and eglplatform_fbdev.
    write('var/lib/environment/compositor/droid-hal-device-leo.conf',
          'EGL_PLATFORM=fbdev\nQT_QPA_PLATFORM=hwcomposer\n'
          'QT_QPA_EGLFS_PHYSICAL_WIDTH=56\nQT_QPA_EGLFS_PHYSICAL_HEIGHT=94\n'
          'LIPSTICK_OPTIONS=-plugin evdevtouch:/dev/touchscreen -plugin evdevkeyboard:keymap=/usr/share/qt5/keymaps/droid.qmap\n'
          'QT_COMPOSITOR_NEGATE_INVERTED_Y=0\n')
    write('etc/mce/99-hd2.ini','[Display]\nBrightnessDirectory=/sys/class/leds/lcd-backlight\n'
          '\n[KeyPad]\nBrightnessDirectory=/sys/class/leds/button-backlight\n')
    # Eliminate the donor's slide-keyboard and Xperia magnetometer rotation overrides.
    write('etc/mce/90evdev.ini','[EVDEV]\n# HD2 has no sliding keyboard.\n')
    sensor=(DONOR/'etc/sensorfw/primaryuse.conf').read_text().replace('"-1,0,0,0,1,0,0,0,1"','"1,0,0,0,1,0,0,0,1"')
    write('etc/sensorfw/primaryuse.conf',sensor)
    write('etc/systemd/journald.conf','[Journal]\nStorage=volatile\nRuntimeMaxUse=8M\nForwardToKMsg=no\n')
    # Old systemd does not support modern service hardening/mount namespaces.
    # Retain its own unit syntax and do not run host systemctl against the image.
    write('usr/local/sbin/hd2-logs', '''#!/bin/sh
dir=/run/hd2-sd/HD2-SF
[ -d "$dir" ] || exit 0
count=0
while [ "$count" -lt 40 ]; do
    dmesg > "$dir/dmesg-systemd.log" 2>&1
    journalctl -b -n 1500 --no-pager > "$dir/journal.log" 2>&1
    systemctl --failed --no-pager > "$dir/failed-units.log" 2>&1
    cat /proc/bus/input/devices > "$dir/input-devices.log"
    cat /proc/mounts > "$dir/mounts.log"
    LD_LIBRARY_PATH=/usr/libexec/droid-hybris/system/lib:/vendor/lib:/system/lib:/system/lib/egl \
        /usr/libexec/droid-hybris/system/bin/logcat -d -t 1000 -v threadtime > "$dir/android-logcat.log" 2>&1
    sync
    count=$((count + 1))
    sleep 15
done
''',0o755)
    unit('hd2-logs.service','[Unit]\nDescription=HD2 first-boot SD logs\n'
         'DefaultDependencies=no\nAfter=systemd-journald.service\n'
         'Conflicts=shutdown.target\nBefore=shutdown.target\n\n'
         '[Service]\nExecStart=/usr/local/sbin/hd2-logs\n', 'basic.target')
    # Diagnostic busybox is static, allowing a shell even if the Android HAL fails.
    shutil.copy2(ROOT/'sources/device-leo/ramdisk/bin/busybox',STAGE/'usr/local/sbin/hd2-busybox')
    (STAGE/'usr/local/sbin/hd2-busybox').chmod(0o755)
    write('usr/local/sbin/hd2-usb-debug','''#!/bin/sh
[ -f /run/hd2-sd/HD2-SF/DEBUG_USB ] || exit 0
[ ! -w /sys/class/usb_composite/rndis/enable ] || echo 1 > /sys/class/usb_composite/rndis/enable
/usr/local/sbin/hd2-busybox ifconfig usb0 192.168.2.15 netmask 255.255.255.0 up || exit 1
exec /usr/local/sbin/hd2-busybox telnetd -F -b 192.168.2.15:23 -l /bin/sh
''',0o755)
    unit('hd2-usb-debug.service','[Unit]\nDescription=Opt-in HD2 USB debug shell\n'
         'After=local-fs.target\nConditionPathExists=/run/hd2-sd/HD2-SF/DEBUG_USB\n\n'
         '[Service]\nExecStart=/usr/local/sbin/hd2-usb-debug\n', 'basic.target')
    # Do not expose the loop backing card as USB mass storage through Xperia settings.
    # Do not claim an official adaptation update channel for this local experiment.
    ssu=(DONOR/'etc/ssu/ssu.ini').read_text()
    ssu=ssu.replace('disabled-repos=home, adaptation0','disabled-repos=home, adaptation0, anzu, xperia_common, extra')
    write('etc/ssu/ssu.ini',ssu)
    patch_systemd()
    shutil.copy2(ROOT/'out/sailfish-debug-tools/systemd',STAGE/'lib/systemd/systemd')
    configure_sailfish(STAGE)
    configure_legacy(STAGE)
    configure_hardware(STAGE)
    shutil.copy2(patch_qpa(), STAGE/QPA_PATH)
    graphics = patch_gralloc()
    for name in GRALLOC_PATHS:
        shutil.copy2(graphics/name, STAGE/name)
    status={'status':'assembled-experimental-NOT-HARDWARE-TESTED',
            'sailfish':'2.0.1.11','android':'NexusHD2 CM11 V4.0 / Android 4.4.1',
            'hybris_donor':'anzu 2.0.1.11 alpha4 / CM11',
            'kernel':'tytung 2.6.32 kitkat with systemd configuration',
            'platform_libraries_from_hd2':replaced,
            'known_unresolved':['No physical HD2 boot or hardware verification',
              'Private Qualcomm/PMEM graphics and droidmedia ABI compatibility unverified',
              'systemd 208 on this kernel configuration unverified; no CONFIG_FHANDLE',
              'Audio, modem, Wi-Fi, sensors, camera and suspend unverified',
              'Xperia RPM package metadata remains; this is not an OTA-supported adaptation',
              'USB debug only; Sailfish USB mode UI is disabled for legacy gadget safety']}
    write('etc/hd2-build-status.json',json.dumps(status,indent=2)+'\n')
    out=ROOT/'out/sailfish-alpha0/HD2-SF'
    out.mkdir(parents=True,exist_ok=True)
    (out/'BUILD-STATUS.json').write_text(json.dumps(status,indent=2)+'\n')
    print(STAGE)

if __name__=='__main__':main()
