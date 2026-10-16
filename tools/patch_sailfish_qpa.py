#!/usr/bin/env python3
"""Match the HD2 RGBX framebuffer in the archived Sailfish Qt HWC plugin."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path('usr/lib/qt5/plugins/platforms/libhwcomposer.so')


def main():
    source = ROOT/'work/sailfish-anzu-rootfs'/RELATIVE
    data = bytearray(source.read_bytes())
    # HwComposerContext::surfaceFormatFor(), 32-bit branch. setAlphaBufferSize
    # is the ARM PLT entry at 0xe794; BLX at 0xecec follows movs r1,#8.
    # HD2 gralloc reports HAL_PIXEL_FORMAT_RGBX_8888 (2), so request zero alpha.
    offset = 0xecea
    assert data[offset:offset+6] == bytes.fromhex('0821fff752ed')
    data[offset:offset+2] = bytes.fromhex('0021')
    output = ROOT/'out/sailfish-debug-tools/libhwcomposer.so'
    output.write_bytes(data)
    output.chmod(0o755)
    record = {'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(data).hexdigest(),
              'file_offset': hex(offset), 'old': '0821', 'new': '0021',
              'change': 'Qt HWC 32-bit framebuffer alpha size 8 -> 0 (RGBX)',
              'evidence': 'logs/sailfish-first-boot/egl-configs.log',
              'runtime_verified': False}
    (ROOT/'logs/sailfish-qpa-patch.json').write_text(json.dumps(record,indent=2)+'\n')
    return output


if __name__ == '__main__':
    print(main())
