#!/usr/bin/env python3
"""Install always-on root ADB in the Smartisan NativeSD ramdisk."""
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
    # This old wpa_supplicant exposes its interface socket in
    # /data/misc/wifi/sockets. The extra Android global socket makes the mixed
    # Smartisan userspace bind @android:wpa_wlan0 twice and exit with EADDRINUSE.
    device_init = device_init.replace(
        '    -Dwext -iwlan0 -c/data/misc/wifi/wpa_supplicant.conf \\\n'
        '    -g@android:wpa_wlan0\n',
        '    -Dwext -iwlan0 -c/data/misc/wifi/wpa_supplicant.conf\n')
    wpa_start = device_init.index('service wpa_supplicant ')
    wpa_end = device_init.index('\n# DHCPCD', wpa_start)
    wpa_block = device_init[wpa_start:wpa_end]
    if 'socket wpa_wlan0 ' not in wpa_block:
        wpa_block = wpa_block.replace(
            '    class main\n',
            '    class main\n    socket wpa_wlan0 dgram 0660 wifi wifi\n',
            1,
        )
        device_init = device_init[:wpa_start] + wpa_block + device_init[wpa_end:]
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


if __name__ == '__main__':
    from firmware import pack_cpio
    boot=ROOT/'out/smartisan-alpha0/HD2-SM20/initrd.gz'
    boot.write_bytes(pack_cpio(configure_smartisan_ramdisk(unpack_cpio(boot.read_bytes()))))
    print('Updated Smartisan ramdisk for always-on USB debugging.')
