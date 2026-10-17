#!/usr/bin/env python3
"""Collect Smartisan-on-HD2 boot diagnostics over USB ADB without writes.

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
            probe = 'getprop ro.smartisan.version; getprop ro.build.description'
            try:
                identity = subprocess.run(['adb', '-s', connected[0], 'shell', probe],
                                          capture_output=True, text=True, timeout=8).stdout.lower()
            except subprocess.TimeoutExpired:
                identity = ''
            if 'smartisan' in identity or 'user-sfo' in identity:
                break
        if time.monotonic() >= deadline:
            raise SystemExit('No Smartisan ADB device found. Recovery does not verify an OS boot.')
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
        'early-boot.txt': 'cat /boot-sd/HD2-SM20/early-boot.log /sdcard/HD2-SM20/early-boot.log 2>/dev/null',
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
