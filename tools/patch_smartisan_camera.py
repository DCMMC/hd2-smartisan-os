#!/usr/bin/env python3
"""Map the HD2 camera's 32-bit long offset to donor Binder's 32-bit int ABI."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'work/hd2-base/system/lib/libcamera.so'
    data = source.read_bytes()
    old = b'_ZN7android10MemoryBaseC1ERKNS_2spINS_11IMemoryHeapEEElj\0'
    new = b'_ZN7android10MemoryBaseC1ERKNS_2spINS_11IMemoryHeapEEEij\0'
    assert data.count(old) == 1 and len(old) == len(new)
    assert new in (ROOT/'work/smartisan-donor/system/lib/libbinder.so').read_bytes()
    patched = data.replace(old, new)
    (ROOT/'work/smartisan-compat/libcamera.so').write_bytes(patched)
    (ROOT/'logs/smartisan-camera-patch.json').write_text(json.dumps({
        'input_sha256': hashlib.sha256(data).hexdigest(),
        'output_sha256': hashlib.sha256(patched).hexdigest(),
        'status': 'Missing constructor import repaired; camera operation unverified'}, indent=2)+'\n')


if __name__ == '__main__': main()
