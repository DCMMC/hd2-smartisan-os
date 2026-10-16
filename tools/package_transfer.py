#!/usr/bin/env python3
"""Create compressed rootfs deliveries for extraction through Recovery ADB."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/sd-transfer'


def prepare(group):
    src=ROOT/'out'/group
    dst=OUT/src.name
    dst.mkdir(parents=True,exist_ok=True)
    for p in src.iterdir():
        if p.is_file() and p.name not in ['rootfs.ext4','SHA256SUMS']:
            shutil.copyfile(p,dst/p.name)
    image=src/'rootfs.ext4'
    temporary=dst/'rootfs.ext4.gz.tmp'
    with image.open('rb') as original, temporary.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=1,mtime=0) as packed:
            shutil.copyfileobj(original,packed,4*1024*1024)
    temporary.replace(dst/'rootfs.ext4.gz')
    with image.open('rb') as f:
        checksum=hashlib.file_digest(f,'sha256').hexdigest()
    (dst/'ROOTFS-UNPACKED.sha256').write_text(checksum+'  rootfs.ext4\n')
    shutil.copyfile(ROOT/'configs/hd2-unpack.sh',dst/'unpack-rootfs.sh')
    with (dst/'SHA256SUMS').open('w') as sums:
        for p in sorted(dst.iterdir()):
            if p.is_file() and p.name!='SHA256SUMS':
                with p.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
                sums.write(checksum+'  '+p.name+'\n')
    print(src.name, 'compressed image bytes:', (dst/'rootfs.ext4.gz').stat().st_size,flush=True)


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(prepare,['smartisan-alpha0/HD2-SM20','sailfish-alpha0/HD2-SF']))
    (OUT/'recovery-unpack.sh').write_text('''#!/sbin/sh
set -e
sd=${1:-/sdcard}
export BB=/sbin/busybox
for name in HD2-SM20 HD2-SF; do
    "$BB" sh "$sd/$name/unpack-rootfs.sh" "$sd/$name"
done
sync
echo 'Both 2 GiB root images are extracted. Boot folders are HD2-SM20 and HD2-SF.'
''')
    print(OUT,flush=True)


if __name__=='__main__':main()
