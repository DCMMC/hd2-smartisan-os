#!/usr/bin/env python3
"""Read back small boot files and image samples after the SD copy."""
import json
import os
from pathlib import Path
from install_sd import ROOT,SD,validate_card,digest

validate_card()
report={}
for group in ['smartisan-alpha0/HD2-SM20','sailfish-alpha0/HD2-SF']:
    source=ROOT/'out'/group
    target=SD/source.name
    sums={line.split()[1]:line.split()[0] for line in (source/'SHA256SUMS').read_text().splitlines()}
    for name in ['zImage','initrd.gz']:
        with (target/name).open('rb') as f:
            os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
        if digest(target/name)!=sums[name]:raise SystemExit('Boot file mismatch: '+str(target/name))
    size=(source/'rootfs.ext4').stat().st_size
    if (target/'rootfs.ext4').stat().st_size!=size:raise SystemExit('Image size mismatch')
    sample=1024*1024
    offsets=[0,size//4,size//2,size*3//4,size-sample]
    with (source/'rootfs.ext4').open('rb') as src,(target/'rootfs.ext4').open('rb') as dst:
        os.posix_fadvise(dst.fileno(),0,0,os.POSIX_FADV_DONTNEED)
        for offset in offsets:
            src.seek(offset);dst.seek(offset)
            if src.read(sample)!=dst.read(sample):raise SystemExit('SD image sample mismatch at '+str(offset))
    report[source.name]={'boot_files_sha256':'matched','image_bytes':size,
                        'image_sample_offsets':offsets,'sample_bytes':sample,
                        'full_sd_image_hash_checked':False,'phone_boot_tested':False}
(ROOT/'logs/sd-readback.json').write_text(json.dumps(report,indent=2)+'\n')
print('Boot file SHA-256 and five image samples per OS match. No phone boot test.')
