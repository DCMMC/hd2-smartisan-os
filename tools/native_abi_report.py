#!/usr/bin/env python3
"""Check the native-link boundary between Smartisan framework and HD2 libraries.

This is a static blocker report, not a claim that symbol-complete libraries boot.
Uses the dependency closure (more permissive than older Android linkers).
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'work/hd2-base/system'
DONOR = ROOT/'work/smartisan-donor/system'
TARGETS = ['libandroid_runtime.so','libandroid_servers.so','libbinder.so',
           'libgui.so','libsurfaceflinger.so','libui.so','libqdMetaData.so',
           'libandroidfw.so','libinput.so','libinputservice.so']

@lru_cache(None)
def elf(path):
    dynamic = subprocess.check_output(['readelf','-d','-W',str(path)],text=True)
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
    symbols = subprocess.check_output(['readelf','--dyn-syms','-W',str(path)],text=True)
    imports, exports = set(), set()
    for line in symbols.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].rstrip(':').isdigit():
            continue
        name = parts[7].split('@')[0]
        if parts[6] == 'UND' and parts[4] == 'GLOBAL':
            imports.add(name)
        elif parts[6] != 'UND' and parts[4] in ('GLOBAL','WEAK'):
            exports.add(name)
    return needed, imports, exports

def find(name):
    if name in TARGETS:
        return DONOR/'lib'/name
    for directory in [BASE/'lib',BASE/'vendor/lib']:
        path = directory/name
        if path.exists():
            return path
    return None

def main():
    report = {}
    for name in TARGETS:
        path = DONOR/'lib'/name
        needed, imports, own_exports = elf(path)
        exported, seen, missing = set(own_exports), set(), set()
        pending = needed.copy()
        while pending:
            dependency = pending.pop()
            if dependency in seen:
                continue
            seen.add(dependency)
            match = find(dependency)
            if match is None:
                missing.add(dependency)
                continue
            child, _, symbols = elf(match)
            exported.update(symbols)
            pending.extend(child)
        # Bionic exports these from the linker, not its stub libdl.so.
        exported.update(['dlopen','dlclose','dlsym','dlerror','dladdr','android_update_LD_LIBRARY_PATH'])
        unresolved = sorted(imports-exported)
        report[name] = {'missing_libraries':sorted(missing),'unresolved_symbols':unresolved,
                        'dependency_closure':sorted(seen)}
    output = ROOT/'out/smartisan-native-abi.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    for name,result in report.items():
        print(name, 'missing libraries:',len(result['missing_libraries']),
              'unresolved symbols:',len(result['unresolved_symbols']))
    print(output)

if __name__ == '__main__':
    main()
