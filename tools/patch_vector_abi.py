#!/usr/bin/env python3
"""Adapt this NexusHD2 libutils to both CM legacy and Smartisan vtables.

Only the three SortedVector comparison calls change. All object fields and
other virtual slots were compared in the input binaries and are identical.
The selector occupies existing zero padding after the executable segment.
"""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def branch_link(site, target):
    offset=target-(site+4)
    assert offset % 2 == 0 and -(1<<24) <= offset < (1<<24)
    sign=(offset>>24)&1
    j1=1^((offset>>23)&1)^sign
    j2=1^((offset>>22)&1)^sign
    return struct.pack('<HH',0xf000|(sign<<10)|((offset>>12)&0x3ff),
                       0xd000|(j1<<13)|(j2<<11)|((offset>>1)&0x7ff))


def main():
    out=ROOT/'work/smartisan-compat'
    cross=str(ROOT/'sources/toolchain-4.4.3/bin/arm-eabi-')
    subprocess.run([cross+'as','-march=armv7-a',str(ROOT/'configs/smartisan-compat/vector.S'),
                    '-o',str(out/'vector.o')],check=True)
    subprocess.run([cross+'ld','-Ttext=0x136c4','-e','hd2_vector_compare',
                    str(out/'vector.o'),'-o',str(out/'vector.elf')],check=True)
    subprocess.run([cross+'objcopy','-O','binary','-j','.text',str(out/'vector.elf'),
                    str(out/'vector.bin')],check=True)
    original=(ROOT/'work/hd2-base/system/lib/libutils.so').read_bytes()
    data=bytearray(original)
    edits={0x105f8:(bytes.fromhex('1b6c'),bytes.fromhex('00bf')),
           0x10604:(bytes.fromhex('98470028'),branch_link(0x10604,0x136c4)),
           0x106ae:(bytes.fromhex('1b6c'),bytes.fromhex('00bf')),
           0x106b4:(bytes.fromhex('98470028'),branch_link(0x106b4,0x136c4)),
           0x106d8:(bytes.fromhex('036c'),bytes.fromhex('0346')),
           0x106dc:(bytes.fromhex('984729460028'),branch_link(0x106dc,0x136c4)+bytes.fromhex('2946'))}
    for offset,(before,after) in edits.items():
        assert data[offset:offset+len(before)]==before,hex(offset)
        assert len(before)==len(after)
        data[offset:offset+len(before)]=after
    helper=(out/'vector.bin').read_bytes()
    assert len(helper)<128 and data[0x136c4:0x136c4+len(helper)]==bytes(len(helper))
    data[0x136c4:0x136c4+len(helper)]=helper
    # Third program header is the existing read/execute LOAD segment.
    ph=52+2*32
    assert struct.unpack_from('<8I',data,ph)==(1,0,0,0,0x136c4,0x136c4,5,0x1000)
    struct.pack_into('<II',data,ph+16,0x136c4+len(helper),0x136c4+len(helper))
    (out/'libutils.so').write_bytes(data)
    report={'input_sha256':hashlib.sha256(original).hexdigest(),
            'output_sha256':hashlib.sha256(data).hexdigest(),
            'compare_call_sites':[hex(x) for x in (0x10604,0x106b4,0x106dc)],
            'selector_address':'0x136c4','selector_bytes':len(helper)}
    (ROOT/'logs/smartisan-vector-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
