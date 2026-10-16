#!/usr/bin/env python3
"""Map the donor-only Runtime.gcAndTrim API onto CM Dalvik's supported GC.

This preserves garbage collection, but does not implement Smartisan's extra
native heap trimming. No Dalvik internal structures or native ABI are changed.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'gcAndTrim-calls-gc-v1'


def main():
    source = ROOT/'work/smartisan-donor/system/framework/core.jar'
    out = ROOT/'work/smartisan-compat'
    output = out/'core.jar'
    report_path = ROOT/'logs/smartisan-core-patch.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists() and report_path.exists():
        previous = json.loads(report_path.read_text())
        if (previous.get('recipe') == RECIPE and
            previous.get('source_sha256') == source_hash and
            previous.get('output_sha256') == hashlib.sha256(output.read_bytes()).hexdigest()):
            print(output)
            return
    smali = out/'core-smali'
    cp = str(ROOT/'sources/smali-jars/*')
    subprocess.run(['java', '-cp', cp, 'org.jf.baksmali.Main', 'disassemble',
                    '--jobs', '1', '-o', str(smali), str(source)], check=True)
    runtime = smali/'java/lang/Runtime.smali'
    text = runtime.read_text()
    before = '.method public native gcAndTrim()V\n.end method'
    after = '''.method public gcAndTrim()V
    .registers 1
    invoke-virtual {p0}, Ljava/lang/Runtime;->gc()V
    return-void
.end method'''
    assert text.count(before) == 1
    runtime.write_text(text.replace(before, after))
    dex = out/'core.dex'
    subprocess.run(['java', '-cp', cp, 'org.jf.smali.Main', 'assemble',
                    '--jobs', '1', str(smali), '-o', str(dex)], check=True)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, 'w') as new:
        for entry in old.infolist():
            new.writestr(entry, dex.read_bytes() if entry.filename == 'classes.dex'
                         else old.read(entry.filename))
    report = {'recipe': RECIPE, 'source_sha256': source_hash,
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'change': 'Runtime.gcAndTrim calls Runtime.gc; extra heap trimming unavailable'}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__': main()
