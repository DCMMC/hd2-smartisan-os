#!/usr/bin/env python3
"""Run under fakeroot; create a regular image file compatible with Linux 2.6.32."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('image',type=Path)
    ap.add_argument('--size-mib',type=int,default=2048)
    ap.add_argument('--permissions',type=Path)
    ap.add_argument('--metadata',type=Path,help='Numeric tar metadata for a Linux rootfs')
    ap.add_argument('--label',default='HD2-SM20')
    args=ap.parse_args()
    if not os.environ.get('FAKEROOTKEY'):
        raise SystemExit('Run using fakeroot -- python3 tools/make_ext4.py ...')
    if not 1536 <= args.size_mib <= 4095:
        raise SystemExit('Image must fit within the FAT32 single-file limit')
    root=args.source.resolve()
    metadata=json.loads(args.metadata.read_text()) if args.metadata else {}
    for path in [root]+list(root.rglob('*')):
        # Never chmod/chown through a rootfs directory symlink on the build host.
        if any(parent.is_symlink() for parent in path.parents if parent!=root and root in parent.parents):
            raise ValueError('Metadata path traverses symlink: '+str(path))
        os.chown(path,0,0,follow_symlinks=False)
        if not args.metadata and not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
        item=metadata.get(str(path.relative_to(root)))
        if item:
            os.chown(path,item['uid'],item['gid'],follow_symlinks=False)
            if not path.is_symlink():path.chmod(item['mode'])
    def apply(path,uid,gid,dmode,fmode,recursive):
        targets=[path]+(list(path.rglob('*')) if recursive and path.is_dir() else [])
        for target in targets:
            if target.exists() or target.is_symlink():
                os.chown(target,uid,gid,follow_symlinks=False)
                if not target.is_symlink():target.chmod(dmode if target.is_dir() else fmode)
    if args.permissions:
        text=args.permissions.read_text()
        for match in re.finditer(r'\b(set_perm_recursive|set_perm)\((.*?)\);',text,re.S):
            parts=[s.strip() for s in match[2].split(',')]
            recursive=match[1]=='set_perm_recursive'
            expected=5 if recursive else 4
            if len(parts)!=expected or not parts[-1].startswith('"/system/') and parts[-1]!='"/system"':
                continue
            name=parts[-1].strip('"').lstrip('/')
            if '..' in Path(name).parts:raise ValueError('Unsafe metadata path')
            uid,gid=int(parts[0]),int(parts[1])
            dm=int(parts[2],8);fm=int(parts[3],8) if recursive else dm
            apply(root/name,uid,gid,dm,fm,recursive)
    if (root/'data').exists():apply(root/'data',1000,1000,0o771,0o644,False)
    if (root/'cache').exists():apply(root/'cache',1000,2001,0o771,0o644,False)
    image=args.image.resolve()
    if image.exists():raise SystemExit('Refusing to overwrite existing image: '+str(image))
    image.parent.mkdir(parents=True,exist_ok=True)
    with image.open('xb') as f:f.truncate(args.size_mib*1024*1024)
    features='none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,flex_bg,sparse_super,large_file,uninit_bg,dir_nlink,extra_isize'
    subprocess.run(['mkfs.ext4','-q','-F','-b','4096','-I','256','-m','0',
                    '-O',features,'-E','root_owner=0:0,lazy_itable_init=0,lazy_journal_init=0',
                    '-L',args.label,'-d',str(root),str(image)],check=True)
    print(image)

if __name__=='__main__':main()
