#!/usr/bin/env python3
"""Select packaged textures and fit launcher pixel geometry to HD2 480x800.

The resource integer values and a texture path index change. All bitmap assets,
manifest, resource IDs and remaining DEX offsets stay intact. This is a system
image APK patch; the original manifest certificate is retained for the trusted
KitKat /system scan. It is not an independently installable/resigned APK.
"""
from pathlib import Path
import hashlib
import json
import struct
import zipfile
import zlib
from launcher_resources import fit_hd2

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'work/smartisan-donor/system/priv-app/LauncherSmartisanNew.apk'
    output = ROOT/'work/smartisan-compat/LauncherSmartisanNew.apk'
    with zipfile.ZipFile(source) as archive:
        dex = bytearray(archive.read('classes.dex'))
        assert dex[:8] == b'dex\n035\0'
        count, table = struct.unpack_from('<II', dex, 56)
        strings = {}
        for i in range(count):
            pos = struct.unpack_from('<I', dex, table+4*i)[0]
            while dex[pos] & 128: pos += 1
            pos += 1
            value = bytes(dex[pos:dex.index(0, pos)])
            if value in (b'720p', b'1080p'): strings[value] = i
        pattern = b'\x1a\0'+struct.pack('<H', strings[b'720p'])+b'\x11\0'
        assert dex.count(pattern) == 1
        pos = dex.index(pattern)
        assert pos == 0xe6f52, 'Unexpected donor method layout'
        struct.pack_into('<H', dex, pos+2, strings[b'1080p'])
        dex[12:32] = hashlib.sha1(dex[32:]).digest()
        struct.pack_into('<I', dex, 8, zlib.adler32(dex[12:]) & 0xffffffff)
        resources, resource_changes = fit_hd2(archive.read('resources.arsc'))
        with zipfile.ZipFile(output, 'w') as patched:
            for entry in archive.infolist():
                content = {'classes.dex': dex, 'resources.arsc': resources}.get(entry.filename)
                patched.writestr(entry, content if content is not None else archive.read(entry.filename))
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'dex_instruction_offset': hex(pos),
              'change': 'Packaged 1080p textures; 480x800 geometry and scaled pixel dimensions',
              'resource_changes': resource_changes}
    (ROOT/'logs/smartisan-launcher-patch.json').write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__': main()
