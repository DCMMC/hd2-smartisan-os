#!/usr/bin/env python3
"""Find obvious missing Android dependencies; does not prove HAL ABI compatibility."""
import json
from pathlib import Path
from native_abi_report import elf

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'work/sailfish-stage'
HYBRIS=STAGE/'usr/libexec/droid-hybris/system'
DIRECTORIES=[HYBRIS/'lib',STAGE/'system/vendor/lib',STAGE/'system/lib',STAGE/'system/lib/egl']

def find(name):
    for folder in DIRECTORIES:
        path=folder/name
        if path.is_file():return path
    return None

targets=list((STAGE/'system/lib/hw').glob('*.so'))
targets+=list((STAGE/'system/lib/egl').glob('*.so'))
targets += [STAGE/'system/lib/libhtc_ril.so',STAGE/'system/bin/rild',
            HYBRIS/'bin/servicemanager',HYBRIS/'bin/minisfservice',HYBRIS/'bin/minimediaservice']
report={}
linker={'dlopen','dlclose','dlsym','dlerror','dladdr','android_update_LD_LIBRARY_PATH'}
for path in targets:
    visited={};missing=set();pending=[path]
    while pending:
        item=pending.pop()
        if item.name in visited:continue
        needed,imports,exports=elf(item)
        visited[item.name]=(imports,exports)
        for name in needed:
            candidate=find(name)
            if candidate is None:missing.add(name)
            elif name not in visited:pending.append(candidate)
    symbols=linker.copy()
    for imports,exports in visited.values():symbols.update(exports)
    unresolved={name:sorted(imports-symbols) for name,(imports,_) in visited.items() if imports-symbols}
    report[str(path.relative_to(STAGE))]={'missing_libraries':sorted(missing),'unresolved_symbols':unresolved,
        'note':'Permissive transitive dependency closure; not a runtime linker or private struct ABI test.'}
    print(path.name,'missing',sorted(missing),'unresolved',unresolved)
(ROOT/'out/sailfish-native-abi.json').write_text(json.dumps(report,indent=2)+'\n')
