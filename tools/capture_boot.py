#!/usr/bin/env python3
"""Collect HD2 boot diagnostics over USB ADB without changing the phone.

Example: python3 tools/capture_boot.py --wait 300
Recovery connections are skipped unless --recovery is supplied.
"""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial')
    parser.add_argument('--wait', type=int, default=0)
    parser.add_argument('--recovery', action='store_true')
    parser.add_argument('--os', choices=['any', 'smartisan', 'sailfish'], default='any')
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=10)
        rows = [line.split() for line in result.stdout.splitlines()[1:]]
        states = ('device', 'recovery') if args.recovery else ('device',)
        connected = [row[0] for row in rows if len(row) >= 2 and row[1] in states
                     and (not args.serial or args.serial == row[0])]
        if len(connected) > 1:
            raise SystemExit('More than one device: choose the HD2 with --serial.')
        if connected:
            if args.os == 'any':
                break
            probe = ('cat /etc/hd2-port-id /target/etc/hd2-port-id /etc/os-release 2>/dev/null; '
                     'getprop ro.smartisan.version 2>/dev/null; '
                     'if [ -f /hd2-usb-setup ] && [ -d /target ]; then echo sailfish-initramfs; fi')
            try:
                identity = subprocess.run(['adb', '-s', connected[0], 'shell', probe],
                                          capture_output=True, text=True, timeout=8).stdout.lower()
            except subprocess.TimeoutExpired:
                identity = ''
            matches = ('sailfish' in identity) if args.os == 'sailfish' else ('user-sfo' in identity)
            if matches:
                break
        if time.monotonic() >= deadline:
            raise SystemExit('No ADB device matching the requested OS. Recovery does not verify an OS boot.')
        time.sleep(min(3, max(0, deadline - time.monotonic())))
    root = Path(__file__).resolve().parents[1]
    output = root / 'logs' / ('phone-boot-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    output.mkdir(parents=True)
    command = ['adb', '-s', connected[0]]
    checks = {
        'identity.txt': 'id; uname -a; cat /proc/cmdline; cat /etc/hd2-port-id 2>/dev/null',
        'mounts.txt': 'cat /proc/mounts',
        'dmesg.txt': 'dmesg',
        'processes.txt': 'ps',
        'properties.txt': 'getprop',
        'logcat.txt': 'logcat -d -v threadtime',
        'systemd.txt': 'if [ -x /bin/systemctl ]; then /bin/systemctl --no-pager --failed; fi',
        'journal.txt': 'if [ -x /bin/journalctl ]; then /bin/journalctl -b --no-pager -n 500; fi',
        'early-boot.txt': 'cat /sd/HD2-SF/early-boot.log /run/hd2-sd/HD2-SF/early-boot.log 2>/dev/null',
    }
    for filename, script in checks.items():
        with (output / filename).open('wb') as stream:
            try:
                subprocess.run(command + ['shell', script], stdout=stream,
                               stderr=subprocess.STDOUT, timeout=25)
            except subprocess.TimeoutExpired:
                stream.write(b'\nHost capture timed out after 25 seconds.\n')
    print(output)


if __name__ == '__main__':
    main()
