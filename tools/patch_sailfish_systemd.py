#!/usr/bin/env python3
"""Use the legacy kernel's writable tasks interface for systemd cg_attach.

This is a bring-up compatibility patch, not a kernel-wide cgroup.procs
backport. Service children are attached before exec and their later threads
inherit that group. Moving an already multithreaded external process as a
whole remains unverified; this call moves the supplied task only.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'work/sailfish-anzu-rootfs/lib/systemd/systemd'
    original = source.read_bytes()
    data = bytearray(original)
    # cg_attach's PC-relative filename literal. Read/enumeration paths retain
    # cgroup.procs; only the attach write selects the existing "tasks" string.
    literal, add_pc = 0x52658, 0x525cc
    before, after = 0xa7264-(add_pc+4), 0xa7218-(add_pc+4)
    assert data[0x97264:0x97271] == b'cgroup.procs\0'
    assert data[0x97218:0x9721e] == b'tasks\0'
    assert struct.unpack_from('<I',data,literal-0x10000)[0] == before
    struct.pack_into('<I',data,literal-0x10000,after)
    out = ROOT/'out/sailfish-debug-tools/systemd'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(data)
    out.chmod(0o755)
    report = {'input_sha256':hashlib.sha256(original).hexdigest(),
              'output_sha256':hashlib.sha256(data).hexdigest(),
              'literal_address':hex(literal),'reason':__doc__.strip(),
              'upstream_function':'https://github.com/systemd/systemd/blob/v208/src/shared/cgroup-util.c'}
    (ROOT/'logs/sailfish-systemd-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out)


if __name__ == '__main__':
    main()
