#!/usr/bin/env python3
"""Read the known HD2 card through Recovery ADB; optionally correct its FAT32 type.

--fix-fat-type changes only MBR byte 450 from 0x07 to 0x0c, after saving the
original sector locally and verifying the card identity and all partition bounds.
It does not repair filesystems, move partitions, or format anything.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/'backups/ios-before-multipartition-fix-20261017'
DISK='/dev/block/mmcblk0'
EXPECTED=[(64,27262912),(27262976,25165824),(52428864,8640448),(0,0)]


class Recovery:
    def __init__(self,serial=None):
        if serial is None:
            rows=subprocess.check_output(['adb','devices'],text=True).splitlines()[1:]
            devices=[r.split()[0] for r in rows if len(r.split())>=2 and r.split()[1] in ('device','recovery')]
            if len(devices)!=1:raise RuntimeError('Connect exactly one HD2 in Recovery with ADB enabled')
            serial=devices[0]
        self.command=['adb','-s',serial]
        if 'uid=0' not in self.shell('id'):
            raise RuntimeError('Recovery ADB must run as root')
        if int(self.shell('cat /sys/class/block/mmcblk0/size').strip())!=61069312:
            raise RuntimeError('Unexpected SD card size')

    def shell(self,command):
        wrapped=command+'\nhd2_result=$?\necho __HD2_STATUS:$hd2_result'
        result=subprocess.run(self.command+['shell',wrapped],capture_output=True,text=True,check=True)
        text=result.stdout.replace('\r','')
        match=re.search(r'(?m)^__HD2_STATUS:(\d+)\s*$',text)
        if not match or match.group(1)!='0':
            raise RuntimeError('Recovery command failed: '+command+'\n'+text+result.stderr)
        return text[:match.start()]

    def read_sectors(self,start,count,local):
        # This Recovery's old dd wraps large whole-disk seek offsets.
        # Read high partitions through their own block nodes instead.
        if start < 0 or count < 1 or (start + count) * 512 > 2**31:
            raise ValueError('Old Recovery dd cannot safely seek this whole-disk offset')
        temporary='/tmp/hd2-sector-read.bin'
        self.shell(f'/sbin/busybox dd if={DISK} of={temporary} bs=512 skip={int(start)} count={int(count)}')
        subprocess.run(self.command+['pull',temporary,str(local)],check=True,capture_output=True)
        data=local.read_bytes()
        if len(data)!=count*512:raise RuntimeError('Short sector read')
        return data

    def file_size(self,path):
        # The installed 4EXT BusyBox has stat -t, but was built without stat -c.
        result=self.shell('/sbin/busybox stat -t '+shlex.quote(path))
        return int(result.split()[1])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial')
    ap.add_argument('--fix-fat-type',action='store_true')
    args=ap.parse_args()
    recovery=Recovery(args.serial)
    BACKUP.mkdir(parents=True,exist_ok=True)
    readback=ROOT/'work/ios-storage'
    readback.mkdir(parents=True,exist_ok=True)
    mbr=recovery.read_sectors(0,1,readback/'mbr-current.bin')
    if mbr[510:512]!=b'\x55\xaa' or struct.unpack_from('<I',mbr,440)[0]!=0xef7023ea:
        raise RuntimeError('The recorded HD2 MBR identity does not match')
    parts=[]
    for i in range(4):
        entry=mbr[446+16*i:462+16*i]
        start,size=struct.unpack_from('<II',entry,8)
        if (start,size)!=EXPECTED[i]:raise RuntimeError('Partition geometry changed; refusing to modify it')
        parts.append({'number':i+1,'type':entry[4],'flags':entry[0],'start':start,'sectors':size})
    if parts[0]['type'] not in (0x07,0x0b,0x0c) or [p['type'] for p in parts[1:]]!=[0x83,0x04,0]:
        raise RuntimeError('Unexpected partition types')
    bpb=recovery.read_sectors(64,8,readback/'fat32-boot-sectors.bin')
    hidden,total=struct.unpack_from('<II',bpb,28)
    fsid=struct.unpack_from('<I',bpb,67)[0]
    if bpb[510:512]!=b'\x55\xaa' or struct.unpack_from('<H',bpb,11)[0]!=512 or fsid!=0x66c4171f:
        raise RuntimeError('FAT32 boot-sector identity does not match')
    if bpb[82:90]!=b'FAT32   ' or hidden!=64 or not 65525<total<=EXPECTED[0][1]:
        raise RuntimeError('FAT32 BPB needs further investigation before changing the type')
    report={'partitions':parts,'bpb_hidden_sectors':hidden,'bpb_total_sectors':total,
            'bpb_volume_id':f'{fsid:08x}','mbr_sha256':hashlib.sha256(mbr).hexdigest(),
            'fat_type_fixed':False,'phone_boot_verified':False}
    for name,data in [('mbr-original.bin',mbr),('fat32-boot-original.bin',bpb)]:
        p=BACKUP/name
        if not p.exists():
            with p.open('xb') as f:f.write(data)
    print(json.dumps(report,indent=2),flush=True)
    if args.fix_fat_type and parts[0]['type']==0x07:
        current=recovery.read_sectors(0,1,readback/'mbr-before-write.bin')
        if current!=mbr:raise RuntimeError('MBR changed since it was read')
        changed=bytearray(mbr);changed[450]=0x0c
        assert [i for i,(a,b) in enumerate(zip(mbr,changed)) if a!=b]==[450]
        patched=readback/'mbr-fat32-type.bin';patched.write_bytes(changed)
        subprocess.run(recovery.command+['push',str(patched),'/tmp/hd2-mbr-fat32.bin'],check=True)
        recovery.shell('/sbin/busybox dd if=/tmp/hd2-mbr-fat32.bin of='+DISK+' bs=512 count=1 conv=notrunc && sync')
        actual=recovery.read_sectors(0,1,readback/'mbr-after-write.bin')
        if actual!=changed:raise RuntimeError('MBR readback differs from the intended single-byte change')
        report['fat_type_fixed']=True
        report['mbr_after_sha256']=hashlib.sha256(actual).hexdigest()
        print('Corrected FAT32 partition type 0x07 -> 0x0c; all other MBR bytes unchanged.',flush=True)
    (ROOT/'logs/ios-partition-repair.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
