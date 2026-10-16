#!/usr/bin/env python3
"""Adapt Smartisan's CPU scheduling and framebuffer count to the HD2."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'work/smartisan-compat'
    inputs={
        'libcutils.so':(ROOT/'work/hd2-base/system/lib/libcutils.so',
            [(0x4ad2,bytes([3,6,11,6,6]),bytes([3,6,6,6,6]))]),
        'libsurfaceflinger.so':(ROOT/'work/smartisan-donor/system/lib/libsurfaceflinger.so',
            [(0x1fc50,bytes.fromhex('0321'),bytes.fromhex('0221')),
             (0x1fc60,bytes.fromhex('0221'),bytes.fromhex('0121'))]),
    }
    report={}
    for name,(path,edits) in inputs.items():
        original=path.read_bytes(); data=bytearray(original)
        for offset,before,after in edits:
            assert data[offset:offset+len(before)]==before,(name,hex(offset))
            assert len(before)==len(after)
            data[offset:offset+len(before)]=after
        (out/name).write_bytes(data)
        report[name]={'input_sha256':hashlib.sha256(original).hexdigest(),
                      'output_sha256':hashlib.sha256(data).hexdigest(),
                      'offsets':[hex(x[0]) for x in edits]}
    report['reason']=['Scheduling policy 2 uses HD2 foreground CPU cgroup',
        'FramebufferSurface uses two buffers and one acquired buffer, matching the HD2 framebuffer geometry']
    (ROOT/'logs/smartisan-platform-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
