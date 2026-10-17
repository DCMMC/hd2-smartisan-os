#!/usr/bin/env python3
"""Use the HD2 Binder implementation and map Qualcomm's self2() to self().

The leo camera HAL still uses MemoryHeapPmem, which AOSP's 4.4 Binder kept but
the Smartisan/Qualcomm build removed.  Smartisan's libandroid_runtime has one
vendor-only ProcessState::self2() import; leo Binder provides the standard
self() entry point with the same return ABI.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'work/smartisan-compat'
    output.mkdir(exist_ok=True)

    binder_source = ROOT / 'work/hd2-base/system/lib/libbinder.so'
    binder_output = output / 'libbinder.so'
    shutil.copyfile(binder_source, binder_output)

    runtime_source = ROOT / 'work/smartisan-donor/system/lib/libandroid_runtime.so'
    runtime = runtime_source.read_bytes()
    vendor = b'_ZN7android12ProcessState5self2Ev\0'
    standard = b'_ZN7android12ProcessState4selfEv\0'
    assert runtime.count(vendor) == 1
    assert standard in binder_output.read_bytes()
    runtime = runtime.replace(vendor, standard.ljust(len(vendor), b'\0'))
    runtime_output = output / 'libandroid_runtime.so'
    runtime_output.write_bytes(runtime)

    report = {
        'binder_input_sha256': hashlib.sha256(binder_source.read_bytes()).hexdigest(),
        'binder_output_sha256': hashlib.sha256(binder_output.read_bytes()).hexdigest(),
        'runtime_input_sha256': hashlib.sha256(runtime_source.read_bytes()).hexdigest(),
        'runtime_output_sha256': hashlib.sha256(runtime).hexdigest(),
        'runtime_change': 'ProcessState::self2() import mapped to ProcessState::self()',
        'camera_change': 'Restore HD2 MemoryHeapPmem implementation',
    }
    (ROOT / 'logs/smartisan-binder-camera-patch.json').write_text(
        json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
