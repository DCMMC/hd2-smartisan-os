"""Small, unprivileged helpers for Android 4.x ZIPs and newc ramdisks."""
from dataclasses import dataclass
import gzip
from pathlib import Path, PurePosixPath
import stat
import struct
import zipfile

@dataclass
class Entry:
    name: str
    fields: list
    data: bytes

def unpack_cpio(data):
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    offset, result = 0, []
    while offset + 110 <= len(data):
        header = data[offset:offset+110]
        if header[:6] != b'070701':
            raise ValueError('Only newc cpio is supported')
        fields = [int(header[i:i+8], 16) for i in range(6,110,8)]
        offset += 110
        name = data[offset:offset+fields[11]-1].decode()
        offset = (offset + fields[11] + 3) & ~3
        body = data[offset:offset+fields[6]]
        if len(body) != fields[6]:
            raise ValueError('Truncated cpio')
        offset = (offset + fields[6] + 3) & ~3
        if name == 'TRAILER!!!':
            return result
        result.append(Entry(name.removeprefix('./'), fields, body))
    raise ValueError('Missing cpio trailer')

def pack_cpio(entries):
    output = bytearray()
    trailer = Entry('TRAILER!!!', [0,0,0,0,1,0,0,0,0,0,0,11,0], b'')
    for entry in list(entries) + [trailer]:
        fields = entry.fields.copy()
        name = entry.name.encode() + b'\0'
        fields[6], fields[11] = len(entry.data), len(name)
        output.extend(b'070701' + b''.join(f'{v:08x}'.encode() for v in fields))
        output.extend(name)
        output.extend(b'\0' * (-len(output) % 4))
        output.extend(entry.data)
        output.extend(b'\0' * (-len(output) % 4))
    return gzip.compress(bytes(output), compresslevel=9, mtime=0)

def new_entry(name, data=b'', mode=stat.S_IFREG | 0o755, inode=1):
    return Entry(name, [inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name)+1, 0], data)

def boot_ramdisk(data):
    if data[:8] != b'ANDROID!':
        raise ValueError('Not a legacy Android boot image')
    kernel_size, _, ramdisk_size = struct.unpack_from('<3I', data, 8)
    page_size = struct.unpack_from('<I', data, 36)[0]
    if page_size not in (2048,4096,8192,16384):
        raise ValueError('Unsupported Android page size')
    offset = page_size + (kernel_size + page_size - 1) // page_size * page_size
    return data[offset:offset+ramdisk_size]

def extract_zip_system(archive, destination):
    """Extract regular system/ files; reject path traversal and defer symlinks."""
    destination = Path(destination)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe ZIP member: ' + info.filename)
            if not info.filename.startswith('system/'):
                continue
            target = destination.joinpath(*path.parts)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Handle ZIP symlink explicitly: ' + info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            mode = (info.external_attr >> 16) & 0o777
            target.chmod(mode or (0o755 if path.parts[1] in ('bin','xbin') else 0o644))
