#!/usr/bin/env python3
"""Back up specifically authorized old images and install into MAGLDR's FAT32 SD."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
SD=Path('/run/media/DCMMC/HD2_SD')
EXT=Path('/run/media/DCMMC/NativeSD')
BACKUP=ROOT/'backups/fat32-before-hd2-ports-20261017'
OLD={'MIUI':['system.ext4','data.ext4'],
     'MIUI23':['system.ext2','data.img','rootfs.img'],
     'AND5':['system.ext4','data.ext4']}

def validate_card():
    source=subprocess.check_output(['findmnt','-n','-o','SOURCE','--mountpoint',str(SD)],text=True).strip()
    fs=subprocess.check_output(['findmnt','-n','-o','FSTYPE','--mountpoint',str(SD)],text=True).strip()
    info=json.loads(subprocess.check_output(['lsblk','-J','-o','PATH,MODEL,LABEL,FSTYPE',source],text=True))['blockdevices'][0]
    parent=subprocess.check_output(['lsblk','-n','-o','PKNAME',source],text=True).strip()
    physical=Path('/sys/class/block',parent,'device').resolve()
    usb_match=False
    for candidate in physical.parents:
        product=candidate/'product'
        if product.is_file() and product.read_text().strip()=='MAGLDR':
            usb_match=(candidate/'idVendor').read_text().strip()=='045e' and (candidate/'idProduct').read_text().strip()=='ffff'
            break
    if fs!='vfat' or info['label']!='HD2_SD' or not usb_match:
        raise SystemExit('Unexpected storage device; no changes made')
    return source

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def copy_checked(source,target,readback):
    before=source.stat()
    h=hashlib.sha256();done=0;last=0;started=time.monotonic()
    target.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as src,target.open('xb') as dst:
        while data:=src.read(4*1024*1024):
            dst.write(data);h.update(data);done+=len(data)
            if time.monotonic()-last>=10 and before.st_size>16*1024*1024:
                elapsed=max(time.monotonic()-started,0.01)
                print(f'{target.parent.name}/{target.name}: {done//1048576}/{before.st_size//1048576} MiB, {done/1048576/elapsed:.1f} MiB/s',flush=True)
                last=time.monotonic()
        dst.flush();os.fsync(dst.fileno())
    after=source.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise RuntimeError('Source changed during copy: '+str(source))
    if target.stat().st_size!=before.st_size:raise RuntimeError('Destination size mismatch')
    checksum=h.hexdigest()
    if readback and digest(target)!=checksum:raise RuntimeError('Backup verification failed')
    return {'file':str(source),'backup':str(target),'bytes':done,'sha256':checksum}

def main():
    device=validate_card()
    if BACKUP.exists():raise SystemExit('Backup directory exists; inspect it before resuming')
    for name in OLD:
        if not (EXT/name/'.native-copy-complete').is_file():
            raise SystemExit('NativeSD copy marker missing: '+name)
    for name in ['HD2-SM20','HD2-SF']:
        if (SD/name).exists() or (SD/(name+'.copying')).exists():
            raise SystemExit('Destination exists; refusing to overwrite '+name)
    BACKUP.mkdir(parents=True)
    records=[]
    for name in OLD:
        # Keep a complete local backup, including current boot files and user files.
        for path in sorted((SD/name).rglob('*')):
            if path.is_symlink():raise RuntimeError('Unexpected FAT32 symlink')
            if path.is_file():
                target=BACKUP/name/path.relative_to(SD/name)
                records.append(copy_checked(path,target,readback=True))
        (BACKUP/'backup-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
        validate_card()
        for filename in OLD[name]:
            source=SD/name/filename
            # Only the seven explicitly enumerated old image files are removed.
            if source.is_file():source.unlink()
        print('Backed up and removed old FAT32 images:',name,flush=True)
    subprocess.run(['sync','-f',str(SD)],check=True)
    required=sum(p.stat().st_size for group in ['smartisan-alpha0/HD2-SM20','sailfish-alpha0/HD2-SF']
                 for p in (ROOT/'out'/group).iterdir() if p.is_file())
    if shutil.disk_usage(SD).free<required+64*1024*1024:raise RuntimeError('Insufficient FAT32 space')
    installed=[]
    for group in ['smartisan-alpha0/HD2-SM20','sailfish-alpha0/HD2-SF']:
        source=ROOT/'out'/group;name=source.name
        temporary=SD/(name+'.copying');temporary.mkdir()
        checks={line.split()[1]:line.split()[0] for line in (source/'SHA256SUMS').read_text().splitlines()}
        for path in sorted(source.iterdir()):
            if not path.is_file():continue
            result=copy_checked(path,temporary/path.name,readback=False)
            if path.name in checks and result['sha256']!=checks[path.name]:
                raise RuntimeError('Local source differs from package checksum')
        subprocess.run(['sync','-f',str(SD)],check=True)
        temporary.rename(SD/name)
        installed.append(name)
        print('Installed:',SD/name,flush=True)
    subprocess.run(['sync','-f',str(SD)],check=True)
    (BACKUP/'installation.json').write_text(json.dumps({'device':device,'installed':installed,
        'backup':str(BACKUP),'destination':'/run/media/DCMMC/HD2_SD',
        'device_boot_test':False,'sd_full_readback':False},indent=2)+'\n')
    print('SD COPY COMPLETE; no device boot has been performed.',flush=True)

if __name__=='__main__':main()
