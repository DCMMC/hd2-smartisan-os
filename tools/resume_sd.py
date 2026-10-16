#!/usr/bin/env python3
"""Resume only our two SD installations, repairing mismatched partial blocks.

Never removes old ROMs, formats a volume, or alters the partition table.
The previous backup/deletion phase must already have completed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from install_sd import ROOT, SD, BACKUP, digest

GROUPS = ('smartisan-alpha0/HD2-SM20', 'sailfish-alpha0/HD2-SF')
BLOCK = 4 * 1024 * 1024
SYNC_BYTES = 64 * 1024 * 1024


def identify_card(mount):
    record = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-o', 'SOURCE,FSTYPE,OPTIONS', '--mountpoint', str(mount)],
        text=True))['filesystems'][0]
    if record['fstype'] != 'vfat' or 'rw' not in record['options'].split(','):
        raise RuntimeError('The destination must be a writable FAT32 mount')
    source = Path(record['source']).resolve()
    part = json.loads(subprocess.check_output(
        ['lsblk', '-J', '-o', 'PATH,LABEL,PKNAME', str(source)], text=True))['blockdevices'][0]
    if part['label'] != 'HD2_SD' or not part['pkname']:
        raise RuntimeError('Unexpected destination label or parent disk')
    parent = Path(part['pkname']).name
    siblings = json.loads(subprocess.check_output(
        ['lsblk', '-J', '-b', '-o', 'PATH,LABEL,FSTYPE,SIZE', '/dev/' + parent],
        text=True))['blockdevices'][0].get('children', [])
    native = [p for p in siblings if p['label'] == 'NativeSD' and p['fstype'] == 'ext4']
    if len(native) != 1 or len(siblings) != 3:
        raise RuntimeError('The known three-partition HD2 card was not found')
    sys_part = Path('/sys/class/block') / Path(native[0]['path']).name
    if int((sys_part/'start').read_text()) != 27262976 or int((sys_part/'size').read_text()) != 25165824:
        raise RuntimeError('NativeSD partition geometry differs from the recorded card')
    # These retained boot files identify the existing card even in a USB reader.
    manifest = json.loads((BACKUP/'backup-manifest.json').read_text())
    for relative in ('MIUI/initrd.gz', 'MIUI23/initrd.gz'):
        saved = next(p for p in manifest if p['file'] == str(SD/relative))
        if digest(mount/relative) != saved['sha256']:
            raise RuntimeError('Card identity boot-file mismatch: ' + relative)
    return str(source)


def repair_copy(source, target, expected=None):
    """Compare every existing block; a partial file's length is not trusted."""
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise RuntimeError('Unexpected destination type: ' + str(target))
    before = source.stat()
    checked = written = dirty = 0
    checksum = hashlib.sha256()
    started = last = time.monotonic()
    with source.open('rb', buffering=0) as src, target.open(
            'r+b' if target.exists() else 'x+b', buffering=0) as dst:
        os.posix_fadvise(dst.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        while data := src.read(BLOCK):
            checksum.update(data)
            offset = checked
            dst.seek(offset)
            existing = dst.read(len(data))
            if existing != data:
                dst.seek(offset)
                pending = memoryview(data)
                while pending:
                    count = dst.write(pending)
                    if not count:
                        raise OSError('Short SD write')
                    pending = pending[count:]
                written += len(data)
                dirty += len(data)
            checked += len(data)
            if dirty >= SYNC_BYTES:
                os.fdatasync(dst.fileno())
                dirty = 0
            now = time.monotonic()
            if now - last >= 10:
                print(f'{target.parent.name}/{target.name}: {checked//1048576}/{before.st_size//1048576} MiB, '
                      f'rewritten {written//1048576} MiB, {checked/1048576/(now-started):.1f} MiB/s', flush=True)
                last = now
        dst.truncate(before.st_size)
        os.fsync(dst.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('Local source changed during transfer')
    actual = checksum.hexdigest()
    if expected and actual != expected:
        raise RuntimeError('Local source checksum mismatch: ' + str(source))
    return {'file': source.name, 'bytes': checked, 'rewritten_bytes': written, 'sha256': actual}


def verify_files(source, target):
    # Full readback for boot/config files; bounded image readback after fsync.
    report = {}
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        remote = target/path.name
        size = path.stat().st_size
        if remote.stat().st_size != size:
            raise RuntimeError('Destination size mismatch: ' + str(remote))
        with remote.open('rb') as f:
            os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        if path.name != 'rootfs.ext4':
            if digest(path) != digest(remote):
                raise RuntimeError('SD readback mismatch: ' + str(remote))
            continue
        sample = 1024 * 1024
        offsets = [0, size//4, size//2, size*3//4, size-sample]
        with path.open('rb') as src, remote.open('rb') as dst:
            for offset in offsets:
                src.seek(offset)
                dst.seek(offset)
                if src.read(sample) != dst.read(sample):
                    raise RuntimeError(f'SD image sample mismatch at {offset}')
        report = {'image_bytes': size, 'sample_offsets': offsets, 'sample_bytes': sample,
                  'full_sd_image_hash_checked': False, 'phone_boot_tested': False}
    report['small_files_sha256'] = 'matched'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mount', type=Path, default=SD)
    args = parser.parse_args()
    mount = args.mount.resolve()
    device = identify_card(mount)
    records = {}
    for group in GROUPS:
        source = ROOT/'out'/group
        final = mount/source.name
        temporary = mount/(source.name + '.copying')
        if final.exists():
            if temporary.exists():
                raise RuntimeError('Both published and partial directories exist; inspect before resuming')
            records[source.name] = verify_files(source, final)
            print('Already published; readback matched:', final, flush=True)
            continue
        if temporary.is_symlink() or (temporary.exists() and not temporary.is_dir()):
            raise RuntimeError('Unexpected partial destination')
        expected = {line.split()[1]: line.split()[0]
                    for line in (source/'SHA256SUMS').read_text().splitlines()}
        required = sum(max(0, p.stat().st_size - ((temporary/p.name).stat().st_size
                       if (temporary/p.name).is_file() else 0))
                       for p in source.iterdir() if p.is_file())
        if shutil.disk_usage(mount).free < required + SYNC_BYTES:
            raise RuntimeError('Not enough free space to complete this image')
        temporary.mkdir(exist_ok=True)
        transfers = []
        for path in sorted(source.iterdir()):
            if path.is_file():
                transfers.append(repair_copy(path, temporary/path.name, expected.get(path.name)))
        subprocess.run(['sync', '-f', str(mount)], check=True)
        verified = verify_files(source, temporary)
        if identify_card(mount) != device:
            raise RuntimeError('Storage device changed during transfer')
        temporary.rename(final)
        subprocess.run(['sync', '-f', str(mount)], check=True)
        records[source.name] = dict(verified, transfers=transfers)
        (ROOT/'logs/sd-resume.json').write_text(json.dumps(records, indent=2) + '\n')
        print('Installed and read back:', final, flush=True)
    (BACKUP/'installation.json').write_text(json.dumps({
        'device': device, 'destination': str(mount), 'installed': list(records),
        'backup': str(BACKUP), 'device_boot_test': False, 'readback': records}, indent=2) + '\n')
    print('Both folders are complete. Unmount the SD before leaving USB MassStg.', flush=True)


if __name__ == '__main__':
    main()
