#!/usr/bin/env python3
"""Map archived Xperia libhybris allocation callbacks to HD2 alloc_device_t."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {
    'usr/lib/libhybris/eglplatform_fbdev.so': [
        (0x3f50, 'd9f844c0', 'd9f840c0', 'buffer alloc 68 -> 64'),
        (0x2e08, '836c', '436c', 'buffer free 72 -> 68'),
        (0x2c72, '0d46', '0225', 'use two buffers for the 480x1600 HD2 framebuffer')],
    'usr/lib/libhybris-eglplatformcommon.so.1.0.0': [
        (0x53ca, '446c', '046c', 'native buffer alloc 68 -> 64'),
        (0x5dda, '836c', '436c', 'native buffer free 72 -> 68'),
        (0x5f62, 'd0f844c0', 'd0f840c0', 'Wayland server-side buffer alloc 68 -> 64')],
    'usr/lib/libhybris-hwcomposerwindow.so.1.0.0': [
        (0x33ea, 'd9f844c0', 'd9f840c0', 'HWC buffer alloc 68 -> 64'),
        (0x24d8, '836c', '436c', 'HWC buffer free 72 -> 68')],
}


def main():
    records = []
    for name, patches in PATCHES.items():
        original = (ROOT/'work/sailfish-anzu-rootfs'/name).read_bytes()
        data = bytearray(original)
        for offset, before, after, reason in patches:
            old, new = bytes.fromhex(before), bytes.fromhex(after)
            assert data[offset:offset+len(old)] == old, (name, hex(offset))
            data[offset:offset+len(old)] = new
        target = ROOT/'out/sailfish-graphics-patch'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755)
        records.append({'path': name, 'input_sha256': hashlib.sha256(original).hexdigest(),
                        'output_sha256': hashlib.sha256(data).hexdigest(),
                        'patches': patches})
    (ROOT/'logs/sailfish-gralloc-patch.json').write_text(json.dumps(records,indent=2)+'\n')
    return ROOT/'out/sailfish-graphics-patch'


if __name__ == '__main__':
    print(main())
