#!/usr/bin/env python3
"""Run a script over the HD2's existing USB-only root rescue connection."""
import argparse
from pathlib import Path
import re
import shlex
import sys
import pexpect

def run(script, timeout=30):
    child = pexpect.spawn('telnet', ['-b', '192.168.2.14', '192.168.2.15', '2323'],
                          encoding='utf-8', codec_errors='replace', timeout=timeout)
    try:
        child.expect(r'sh-[\d.]+# ')
        child.sendline("stty -echo; set +H; PS1='HD2ROOT> '")
        child.expect(r'\r\nHD2ROOT> ')
        child.sendline('/bin/sh -c '+shlex.quote(script)+
                       "; hd2_rc=$?; printf '\\n__HD2_DONE__:%s\\n' \"$hd2_rc\"")
        child.expect(r'\r\n__HD2_DONE__:(\d+)\r\n')
        return int(child.match.group(1)), child.before.replace('\r', '')
    finally:
        child.close(force=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('script', nargs='?', type=Path)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    status, output = run(args.script.read_text() if args.script else sys.stdin.read(), args.timeout)
    print(output, end='')
    sys.exit(status)
