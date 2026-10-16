#!/usr/bin/env python3
"""Configure services for the HD2 2.6.32 proc interface."""
from pathlib import Path
import subprocess


def configure_legacy(stage):
    # 2.6.32 has oom_adj, not oom_score_adj. systemd 208 aborts service exec
    # with status 206 whenever OOMScoreAdjust is explicitly set, even to 0.
    # v208 cannot clear its 'set' flag through a drop-in, so use full unit
    # overrides without that directive. Leave the kernel default OOM score.
    changed = []
    units = [(p, 'system') for p in (stage/'lib/systemd/system').glob('*.service')]
    units += [(p, 'user') for p in (stage/'usr/lib/systemd/user').glob('*.service')]
    for unit, scope in sorted(units):
        if 'OOMScoreAdjust=' not in unit.read_text():
            continue
        obsolete = stage/'etc/systemd'/scope/(unit.name+'.d')/'hd2-legacy.conf'
        if obsolete.exists():
            obsolete.unlink()
        relative = Path('etc/systemd')/scope/unit.name
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(''.join(line for line in unit.read_text().splitlines(True)
                                  if not line.startswith('OOMScoreAdjust=')))
        changed.append(relative)
    updates = {
        'etc/modules-load.d/hd2.conf': 'fuse\nmsm_rmnet\n',
        'etc/modprobe.d/hd2-wifi.conf':
            'options bcm4329 iface_name=wlan firmware_path=/system/vendor/firmware/fw_bcm4329.bin nvram_path=/proc/calibration\n',
        'etc/systemd/system/hd2-wifi-load.service':
            '[Unit]\nDescription=HD2 Wi-Fi module\nAfter=systemd-udev-settle.service\n'
            '[Service]\nType=simple\nExecStart=/sbin/modprobe bcm4329\n',
        'etc/tmpfiles.d/hd2-user.conf': 'd /run/user/100000 0700 nemo nemo -\n',
        # This kernel has VTs but lacks tty0/active, so logind exposes seat0
        # without VT switching. Register the local console, not unsupported VT7.
        'etc/systemd/system/autologin@.service.d/hd2-console.conf':
            '[Service]\nTTYPath=/dev/console\n',
        'etc/dconf/db/vendor.d/silica-configs.txt':
            '[desktop/sailfish/silica]\ntheme_pixel_ratio=1.0\ndefault_allowed_orientations=1\n',
    }
    for name, text in updates.items():
        relative = Path(name)
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        changed.append(relative)
    relative = Path('etc/systemd/system/multi-user.target.wants/hd2-wifi-load.service')
    target = stage/relative
    if not target.is_symlink():
        target.symlink_to('../hd2-wifi-load.service')
    changed.append(relative)
    relative = Path('etc/systemd/system/dev-mtp.mount')
    target = stage/relative
    if target.is_symlink() or target.exists():
        target.unlink()
    target.symlink_to('/dev/null')
    changed.append(relative)
    # Android executables use the base bionic. Hybris's libc/libdsyscalls pair
    # is for loading Android libraries inside native glibc processes.
    for name in ['usr/local/sbin/hd2-logs', 'usr/bin/droid/droid-hal-startup.sh']:
        relative = Path(name)
        target = stage/relative
        text = target.read_text().replace(
            'LD_LIBRARY_PATH=/usr/libexec/droid-hybris/system/lib',
            'LD_LIBRARY_PATH=/usr/libexec/droid-hybris/lib-dev-alog')
        if name.endswith('/hd2-logs'):
            text = text.replace('dir=/run/hd2-sd/HD2-SF\n[ -d "$dir" ] || exit 0',
                                'dir=/run/hd2-logs\nmkdir -p "$dir" || exit 1')
            text = text.replace('    sync\n', '')
        target.write_text(text)
        changed.append(relative)
    subprocess.run(['dconf', 'compile', str(stage/'etc/dconf/db/vendor'),
                    str(stage/'etc/dconf/db/vendor.d')], check=True)
    changed.append(Path('etc/dconf/db/vendor'))
    return changed


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for path in configure_legacy(root/'work/sailfish-stage'):
        print(path)
