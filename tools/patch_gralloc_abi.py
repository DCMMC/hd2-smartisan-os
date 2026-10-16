#!/usr/bin/env python3
"""Map Smartisan's extended allocation-device slots onto the HD2 gralloc HAL.

The donor has an extra alloc callback at offset 64, shifting normal alloc,
free and dump by one word. Both allocation paths can use the HD2 callback;
the extra trailing argument of the extended path is ignored by ARM EABI.
Framebuffer-device dimensions are unrelated and remain untouched.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT=Path(__file__).resolve().parents[1]


def main():
    original=(ROOT/'work/smartisan-donor/system/lib/libui.so').read_bytes()
    data=bytearray(original)
    patches={0x54ae:(0x6c82,0x6c42,'FramebufferNativeWindow free'),
             0x56ac:(0x6c47,0x6c07,'FramebufferNativeWindow alloc'),
             0x62e8:(0x6cc3,0x6c83,'GraphicBufferAllocator dump'),
             0x6390:(0x6c46,0x6c06,'GraphicBufferAllocator alloc'),
             0x6454:(0x6c83,0x6c43,'GraphicBufferAllocator free')}
    for offset,(before,after,reason) in patches.items():
        assert struct.unpack_from('<H',data,offset)[0]==before,reason
        struct.pack_into('<H',data,offset,after)
    (ROOT/'work/smartisan-compat/libui.so').write_bytes(data)
    report={'input_sha256':hashlib.sha256(original).hexdigest(),
            'output_sha256':hashlib.sha256(data).hexdigest(),
            'patches':{hex(k):v[2] for k,v in patches.items()}}
    (ROOT/'logs/smartisan-gralloc-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
