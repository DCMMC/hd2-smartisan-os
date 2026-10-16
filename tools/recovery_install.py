#!/usr/bin/env python3
"""Transfer the compressed deliveries and unpack them using Recovery ADB.

Run after reviewing/repairing the FAT32 filesystem. Only HD2-SM20, HD2-SF and
their own .copying directories are modified; existing operating systems remain.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from recovery_sd import ROOT, Recovery


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial')
    ap.add_argument('--filesystem-reviewed',action='store_true',required=True)
    args=ap.parse_args()
    recovery=Recovery(args.serial)
    mounts=[line.split() for line in recovery.shell('cat /proc/mounts').splitlines()]
    candidates=[m for m in mounts if m[0]=='/dev/block/mmcblk0p1' and m[2]=='vfat']
    if not candidates:
        recovery.shell('mkdir -p /sdcard && /sbin/busybox mount -t vfat -o rw,noatime /dev/block/mmcblk0p1 /sdcard')
        mount='/sdcard'
    elif len(candidates)==1 and 'rw' in candidates[0][3].split(','):
        mount=candidates[0][1]
    else:raise RuntimeError('Unexpected SD mount state')
    # Volume identity: the two preserved NativeSD boot files from this card.
    for name in ['MIUI/initrd.gz','MIUI23/initrd.gz']:
        size=recovery.file_size(mount+'/'+name)
        backup=ROOT/'backups/fat32-before-hd2-ports-20261017'/name
        if size!=backup.stat().st_size:raise RuntimeError('Unexpected card boot-file identity')
    records={}
    for name in ['HD2-SM20','HD2-SF']:
        source=ROOT/'out/sd-transfer'/name
        final=mount+'/'+name
        partial=final+'.copying'
        already=recovery.shell('if [ -d '+shlex.quote(final)+' ]; then echo yes; else echo no; fi').strip()=='yes'
        if already:
            remote_sums=recovery.shell('cat '+shlex.quote(final+'/SHA256SUMS'))
            if remote_sums!= (source/'SHA256SUMS').read_text():
                raise RuntimeError('A different published build exists; leaving it untouched: '+final)
            print('Matching published folder found; resuming extraction:',final,flush=True)
        else:
            recovery.shell('mkdir -p '+shlex.quote(partial))
            paths=sorted((p for p in source.iterdir() if p.is_file()),
                         key=lambda p:(p.name!='rootfs.ext4.gz',p.name))
            for path in paths:
                target=partial+'/'+path.name+'.transfer'
                print('Sending',name+'/'+path.name,flush=True)
                subprocess.run(recovery.command+['push',str(path),target],check=True)
                size=recovery.file_size(target)
                if size!=path.stat().st_size:raise RuntimeError('Incomplete ADB transfer: '+target)
                recovery.shell('mv '+shlex.quote(target)+' '+shlex.quote(partial+'/'+path.name))
            # This file belongs to the failed original copy, not an installed ROM.
            recovery.shell('rm -f '+shlex.quote(partial+'/rootfs.ext4')+' && sync && mv '+
                           shlex.quote(partial)+' '+shlex.quote(final)+' && sync')
        print('Extracting on the phone:',name,flush=True)
        # Run without captured output so first-boot progress remains visible.
        process=subprocess.Popen(recovery.command+['shell',
            'BB=/sbin/busybox /sbin/busybox sh '+shlex.quote(final+'/unpack-rootfs.sh')+' '+shlex.quote(final)+
            '; hd2_result=$?; echo __HD2_UNPACK_STATUS:$hd2_result'],text=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        output=[]
        for line in process.stdout:
            output.append(line)
            print(line,end='',flush=True)
        result=process.wait()
        if result or '__HD2_UNPACK_STATUS:0' not in ''.join(output):
            raise RuntimeError('Recovery decompression did not finish successfully: '+name)
        size=recovery.file_size(final+'/rootfs.ext4')
        if size!=2147483648:raise RuntimeError('Unexpected extracted image size')
        records[name]={'compressed_bytes':(source/'rootfs.ext4.gz').stat().st_size,
                       'extracted_bytes':size,'recovery_decompression':'gzip CRC and size passed',
                       'phone_boot_tested':False}
        (ROOT/'logs/recovery-install.json').write_text(json.dumps(records,indent=2)+'\n')
    recovery.shell('sync')
    print('Both SD images transferred and extracted; phone boot tests remain.',flush=True)


if __name__=='__main__':main()
