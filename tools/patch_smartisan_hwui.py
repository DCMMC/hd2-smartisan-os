#!/usr/bin/env python3
"""Disable the shared asset atlas on HD2's legacy genlock graphics stack.

Imported atlas images fail GENLOCK_READ_LOCK and produce GL_INVALID_OPERATION.
Returning from the optional atlas init leaves its entry map empty, so HWUI
uses its normal per-bitmap texture upload/cache. GPU rendering stays enabled.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'work/hd2-base/system/lib/libhwui.so'
    data = bytearray(source.read_bytes())
    offset = 0x106ac
    assert data[offset:offset+8] == bytes.fromhex('2de9f3479846354f')
    # Thumb bx lr at AssetAtlas::init(sp<GraphicBuffer>, int*, int) entry.
    data[offset:offset+2] = bytes.fromhex('7047')
    output = ROOT/'work/smartisan-compat/libhwui.so'
    output.write_bytes(data)
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(data).hexdigest(),
              'offset': hex(offset), 'change': 'Disable optional shared texture atlas; keep GPU rendering'}
    (ROOT/'logs/smartisan-hwui-patch.json').write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__': main()
