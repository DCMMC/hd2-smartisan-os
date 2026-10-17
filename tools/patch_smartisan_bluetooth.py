#!/usr/bin/env python3
"""Keep Smartisan's signed Bluetooth APK while disabling its absent QAdapter HAL."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'disable-qadapter-service-v2'


def main():
    source = ROOT/'work/smartisan-donor/system/framework/services.jar'
    output = ROOT/'work/smartisan-compat/services.jar'
    report_path = ROOT/'logs/smartisan-bluetooth-framework-patch.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists() and report_path.exists():
        previous = json.loads(report_path.read_text())
        if (previous.get('recipe') == RECIPE
                and previous.get('source_sha256') == source_hash
                and previous.get('output_sha256') == hashlib.sha256(output.read_bytes()).hexdigest()):
            print(output)
            return

    smali = ROOT/'work/smartisan-bluetooth-services-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)

    manager = smali/'com/android/server/BluetoothManagerService.smali'
    text = manager.read_text()
    pattern = re.compile(
        r'\.method public registerQAdapter\(Landroid/bluetooth/IQBluetoothManagerCallback;\)'
        r'Landroid/bluetooth/IQBluetooth;.*?^\.end method$', re.MULTILINE | re.DOTALL)
    replacement = '''.method public registerQAdapter(Landroid/bluetooth/IQBluetoothManagerCallback;)Landroid/bluetooth/IQBluetooth;
    .registers 2
    .param p1, "callback"    # Landroid/bluetooth/IQBluetoothManagerCallback;

    # The HD2 Bluedroid HAL implements the standard Android 4.4 interface but
    # has no Qualcomm QAdapter extension. Returning null prevents the optional
    # QAdapterService from loading while all standard profiles keep working.
    const/4 v0, 0x0
    return-object v0
.end method'''
    patched, count = pattern.subn(replacement, text)
    if count != 1:
        raise RuntimeError(f'expected one registerQAdapter method, found {count}')
    qbind = re.compile(
        r'    \.line 1268\n'
        r'    new-instance v2, Landroid/content/Intent;\n.*?'
        r'    invoke-virtual \{p0, v2, v5, v4, v6\}, '
        r'Lcom/android/server/BluetoothManagerService;->doBind\('
        r'Landroid/content/Intent;Landroid/content/ServiceConnection;I'
        r'Landroid/os/UserHandle;\)Z\n', re.DOTALL)
    patched, count = qbind.subn(
        '    # HD2 has no Qualcomm IQBluetooth/QAdapter HAL.\n', patched)
    if count != 1:
        raise RuntimeError(f'expected one automatic QAdapter bind, found {count}')
    manager.write_text(patched)

    dex = ROOT/'work/smartisan-compat/services.dex'
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.smali.Main', 'assemble',
        '--jobs', '1', str(smali), '-o', str(dex),
    ], check=True)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, 'w') as new:
        for entry in old.infolist():
            new.writestr(
                entry,
                dex.read_bytes() if entry.filename == 'classes.dex' else old.read(entry.filename),
            )
    report = {
        'recipe': RECIPE,
        'source_sha256': source_hash,
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'change': ('Keep the original signed Smartisan Bluetooth package and '
                   'do not bind its optional Qualcomm QAdapter service; HD2 uses '
                   'the standard Bluedroid adapter and profiles.'),
    }
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
