#!/usr/bin/env python3
"""Extract a tar rootfs without root; defer links and save numeric metadata."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

def relative(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe archive path: '+name)
    return Path(*path.parts)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path)
    ap.add_argument('destination',type=Path)
    ap.add_argument('metadata',type=Path)
    args=ap.parse_args()
    dest=args.destination.resolve()
    if dest.exists():raise SystemExit('Destination must not exist')
    dest.mkdir(parents=True)
    links=[];metadata={}
    with tarfile.open(args.archive,'r|*') as tar:
        for entry in tar:
            name=relative(entry.name)
            if str(name)=='.':continue
            path=dest/name
            metadata[str(name)]={'uid':entry.uid,'gid':entry.gid,'mode':entry.mode,'type':entry.type.decode('ascii')}
            if entry.isdir():path.mkdir(parents=True,exist_ok=True)
            elif entry.isfile():
                path.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(entry) as source,path.open('xb') as target:
                    shutil.copyfileobj(source,target)
                # Preserve exact target modes in metadata; keep the build copy
                # readable/writable by its owner (some source files have mode 000).
                path.chmod(entry.mode | 0o600)
            elif entry.issym() or entry.islnk():
                links.append(entry)
            elif entry.isdev() or entry.isfifo():
                # /dev is mounted as devtmpfs at runtime, never create host devices.
                metadata.pop(str(name),None)
            else:raise ValueError('Unknown archive entry: '+entry.name)
    for entry in links:
        path=dest/relative(entry.name)
        path.parent.mkdir(parents=True,exist_ok=True)
        # No directory symlink may have been followed while writing regular files.
        for parent in path.parents:
            if parent==dest:break
            if parent.is_symlink():raise ValueError('Link traverses another link: '+entry.name)
        if entry.issym():path.symlink_to(entry.linkname)
        else:
            target=dest/relative(entry.linkname)
            if target.is_symlink() or not target.is_file():raise ValueError('Invalid hardlink target')
            os.link(target,path)
    args.metadata.write_text(json.dumps(metadata,indent=2)+'\n')
    print(dest,len(metadata),'entries')

if __name__=='__main__':main()
