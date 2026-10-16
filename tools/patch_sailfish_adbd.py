#!/usr/bin/env python3
"""Let the HD2 static adbd handle an absent early-boot Android property area.

The CM11 bionic property trie assumes /dev/__properties__ was initialized by
Android init. Before that happens, its root pointer is NULL + 128. Treat that
case as an absent property, retaining the existing behavior for valid trees.
"""
from pathlib import Path
import hashlib
import json
import struct
from firmware import unpack_cpio
from patch_vector_abi import branch_link

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'out/sailfish-debug-tools'
    out.mkdir(parents=True, exist_ok=True)
    original = next(e.data for e in unpack_cpio(
        (ROOT/'work/base-boot/boot/boot_NativeSD/initrd.gz').read_bytes())
        if e.name == 'sbin/adbd')
    data = bytearray(original)
    site, stub = 0x1ffb6, 0x2e5c0
    offset = site - 0x8000
    before = bytes.fromhex('2de9f04f85b0')
    assert data[offset:offset+6] == before
    assembly = out/'adbd-property-guard.S'
    assembly.write_text('''.syntax unified
.thumb
.global hd2_property_guard
.thumb_func
hd2_property_guard:
    cmp r0, #128
    bne 1f
    movs r0, #0
    bx lr
1:
    push.w {r4-r11, lr}
    sub sp, #20
    b.w 0x1ffbc
''')
    def branch(site, target):
        first, second = struct.unpack('<HH', branch_link(site, target))
        return struct.pack('<HH', first, second & ~0x4000)
    # cmp r0,#128; bne +4; movs r0,#0; bx lr; original prologue; resume.
    helper = bytes.fromhex('802801d100207047') + before + branch(stub+14,site+6)
    (out/'adbd-property-guard.bin').write_bytes(helper)
    location = stub - 0x8000
    assert len(helper) < 64 and data[location:location+len(helper)] == bytes(len(helper))
    # B.W shares BL's immediate encoding; clear the link instruction bit.
    data[offset:offset+6] = branch(site, stub) + bytes.fromhex('00bf')
    data[location:location+len(helper)] = helper
    assert struct.unpack_from('<8I',data,52) == (1,0,0x8000,0x8000,0x265c0,0x265c0,5,0x1000)
    struct.pack_into('<II',data,52+16,location+len(helper),location+len(helper))
    target = out/'hd2-adbd'
    target.write_bytes(data)
    target.chmod(0o755)
    report = {'input_sha256':hashlib.sha256(original).hexdigest(),
              'output_sha256':hashlib.sha256(data).hexdigest(),
              'property_trie_entry':hex(site),'guard_address':hex(stub),
              'guard_bytes':len(helper),'reason':__doc__.strip()}
    (ROOT/'logs/sailfish-adbd-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(target)


if __name__ == '__main__':
    main()
