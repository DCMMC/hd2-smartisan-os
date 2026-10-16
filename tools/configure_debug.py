#!/usr/bin/env python3
"""Install the user-requested always-on USB debugging in the two SD builds."""
from pathlib import Path
import re
import stat
from firmware import new_entry, unpack_cpio

ROOT = Path(__file__).resolve().parents[1]


def configure_smartisan_ramdisk(entries):
    files = {e.name: e for e in entries}
    def put(name, data, mode=stat.S_IFREG | 0o755):
        if name in files:
            files[name].data = data
            files[name].fields[1] = mode
        else:
            e = new_entry(name, data, mode, inode=max(e.fields[0] for e in entries)+1)
            entries.append(e)
            files[name] = e
    props = dict(line.split('=', 1) for line in files['default.prop'].data.decode().splitlines()
                 if '=' in line and not line.startswith('#'))
    props.update({'ro.secure': '0', 'ro.debuggable': '1', 'ro.adb.secure': '0',
                  'persist.sys.usb.config': 'adb', 'persist.service.adb.enable': '1',
                  'persist.sys.root_access': '3', 'service.adb.root': '1'})
    put('default.prop', ''.join(k+'='+v+'\n' for k,v in props.items()).encode(), stat.S_IFREG | 0o644)
    put('init.usb.rc', (ROOT/'configs/smartisan-usb.rc').read_bytes(), stat.S_IFREG | 0o644)
    put('init.htcleo.usb.rc', b'# USB debug configuration is in /init.usb.rc.\n', stat.S_IFREG | 0o644)
    # The mounted FAT partition contains our live rootfs image. Vold must not
    # attempt to check, unmount, or export it as Android's physical SD card.
    if 'fstab.htcleo' in files:
        fstab = files['fstab.htcleo'].data.decode()
        files['fstab.htcleo'].data = ''.join(line for line in fstab.splitlines(True)
                                             if 'voldmanaged=' not in line).encode()
    device_init = files['init.htcleo.rc'].data.decode()
    device_init = device_init.replace('/storage/sdcard0', '/storage/emulated/legacy')
    device_init = device_init.replace('wpa_supplicant.conf\n', 'wpa_supplicant.conf \\\n')
    files['init.htcleo.rc'].data = device_init.encode()
    init = files['init.rc'].data.decode()
    if 'service hd2-emulated ' not in init:
        init += '''
on post-fs-data
    mkdir /mnt/shell 0711 shell shell
    mkdir /mnt/shell/emulated 0711 shell shell
    mkdir /storage/emulated 0711 root root
    mkdir /storage/emulated/legacy 0000 root root
    mkdir /storage/emulated/0 0000 root root
    mkdir /data/media 0770 media_rw media_rw
    mkdir /data/media/0 0770 media_rw media_rw

service hd2-emulated /system/bin/sdcard -u 1023 -g 1023 -l /data/media /mnt/shell/emulated
    class main
'''
    init = re.sub(r'(?m)(^service adbd .*\n(?:[ \t].*\n|\n)*?)[ \t]+disabled\n', r'\1', init)
    # Keep live logs accessible over ADB without continuously writing to the
    # same FAT card that backs Android's loop filesystem.
    init = init.replace('-f /boot-sd/HD2-SM20/logcat.txt -r 2048 -n 2',
                        '-f /dev/hd2-logcat.txt -r 256 -n 2')
    if 'service hd2-runtime ' not in init:
        init += '''
service hd2-runtime /system/bin/sh /system/bin/hd2-runtime
    class main
    user root
    group root
    oneshot
'''
    files['init.rc'].data = init.encode()
    put('sbin/sh', b'/bin/busybox', stat.S_IFLNK | 0o777)
    put('hd2-unpack.sh', (ROOT/'configs/hd2-unpack.sh').read_bytes())
    helper = files['hd2-mount.sh'].data.decode()
    if '/hd2-unpack.sh' not in helper:
        before='# Android ueventd uses /dev/block;'
        helper=helper.replace(before,
            '$BB --install -s /bin\n'
            '$BB sh /hd2-unpack.sh /boot-sd/HD2-SM20 || fail unpack\n'+before)
        files['hd2-mount.sh'].data=helper.encode()
    return entries


def configure_sailfish(stage):
    def write(name, text, mode=0o644):
        p=stage/name
        if p.is_symlink():p.unlink()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.chmod(mode)
    def link(name, target):
        p=stage/name
        if p.exists() or p.is_symlink():p.unlink()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.symlink_to(target)
    from patch_sailfish_adbd import main as patch_adbd
    patch_adbd()
    adbd=(ROOT/'out/sailfish-debug-tools/hd2-adbd').read_bytes()
    binary=stage/'usr/local/sbin/hd2-adbd'
    binary.write_bytes(adbd)
    binary.chmod(0o755)
    link('sbin/sh','/bin/sh')
    # BusyBox 1.17 recognizes a "busybox" basename, not "hd2-busybox".
    link('usr/local/sbin/busybox','hd2-busybox')
    write('default.prop','ro.hardware=htcleo\nro.secure=0\nro.debuggable=1\n'
          'ro.adb.secure=0\npersist.sys.usb.config=adb\npersist.service.adb.enable=1\n'
          'persist.sys.root_access=3\nservice.adb.root=1\npersist.sys.adb.shell=/bin/sh\n')
    write('usr/local/sbin/hd2-usb-setup',(ROOT/'configs/sailfish-usb-setup').read_text(),0o755)
    for name in ['adbd.service','adbd-prepare.service']:
        link('etc/systemd/system/'+name,'/dev/null')
    write('etc/systemd/system/hd2-adbd.service', '''[Unit]
Description=Always-on HD2 USB ADB
DefaultDependencies=no
After=systemd-udevd.service
Before=basic.target
Conflicts=shutdown.target
Before=shutdown.target

[Service]
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/system/bin
ExecStartPre=/usr/local/sbin/hd2-usb-setup
ExecStart=/usr/local/sbin/hd2-adbd
Restart=always
RestartSec=3
''')
    link('etc/systemd/system/basic.target.wants/hd2-adbd.service','../hd2-adbd.service')
    write('usr/local/sbin/hd2-usb-debug', '''#!/bin/sh
/usr/local/sbin/hd2-usb-setup
/usr/local/sbin/busybox ifconfig usb0 192.168.2.15 netmask 255.255.255.0 up || exit 1
exec /usr/local/sbin/busybox telnetd -F -b 192.168.2.15:23 -l /bin/sh
''',0o755)
    write('etc/systemd/system/hd2-usb-debug.service', '''[Unit]
Description=Always-on HD2 USB root rescue shell
DefaultDependencies=no
After=systemd-udevd.service
Before=basic.target
Conflicts=shutdown.target
Before=shutdown.target

[Service]
ExecStart=/usr/local/sbin/hd2-usb-debug
Restart=always
RestartSec=3
''')
    link('etc/systemd/system/basic.target.wants/hd2-usb-debug.service','../hd2-usb-debug.service')


if __name__ == '__main__':
    from firmware import pack_cpio
    boot=ROOT/'out/smartisan-alpha0/HD2-SM20/initrd.gz'
    boot.write_bytes(pack_cpio(configure_smartisan_ramdisk(unpack_cpio(boot.read_bytes()))))
    configure_sailfish(ROOT/'work/sailfish-stage')
    print('Updated Smartisan ramdisk and Sailfish stage for always-on USB debugging.')
