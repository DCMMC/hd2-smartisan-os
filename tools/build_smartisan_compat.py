#!/usr/bin/env python3
"""Build the old Adreno display API bridge and attach it to eglsubAndroid.

Reuse the optional SONAME entry/string as a NEEDED entry. This preserves all
ELF offsets and load segments for the old Android linker. dlopen uses the
unchanged eglsubAndroid.so filename; the original binary remains in the base.
"""
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'work/smartisan-compat'
    output.mkdir(exist_ok=True)
    subprocess.run([
        str(ROOT/'sources/toolchain-4.4.3/bin/arm-eabi-gcc'),
        '-shared', '-fPIC', '-mthumb', '-march=armv7-a', '-O2', '-nostdlib',
        '-Wl,-soname,libhd2compat.so', '-Wl,--hash-style=sysv', '-Wl,--no-undefined',
        str(ROOT/'configs/smartisan-compat/display.c'),
        '-L'+str(ROOT/'work/smartisan-stage/system/lib'), '-lgui',
        '-o', str(output/'libhd2compat.so'),
    ], check=True)
    data = bytearray((ROOT/'work/hd2-base/system/lib/egl/eglsubAndroid.so').read_bytes())
    assert data[:6] == b'\x7fELF\x01\x01'
    phoff = struct.unpack_from('<I', data, 28)[0]
    phsize, phnum = struct.unpack_from('<HH', data, 42)
    segments = [struct.unpack_from('<8I', data, phoff+i*phsize) for i in range(phnum)]
    dynamic = next(s for s in segments if s[0] == 2)
    tags = {}
    for offset in range(dynamic[1], dynamic[1]+dynamic[4], 8):
        tag, value = struct.unpack_from('<II', data, offset)
        if tag == 0:
            break
        tags[tag] = (offset, value)
    string_address = tags[5][1]
    segment = next(s for s in segments if s[0] == 1 and s[2] <= string_address < s[2]+s[4])
    string_table = segment[1] + string_address - segment[2]
    soname_entry, soname_index = tags[14]
    string_offset = string_table + soname_index
    old = b'eglsubAndroid.so\0'
    new = b'libhd2compat.so\0'
    assert data[string_offset:string_offset+len(old)] == old
    assert len(new) <= len(old)
    data[string_offset:string_offset+len(old)] = new.ljust(len(old), b'\0')
    struct.pack_into('<I', data, soname_entry, 1)
    (output/'eglsubAndroid.so').write_bytes(data)
    print(output)


if __name__ == '__main__':
    main()
