#!/usr/bin/env python3
"""Adapt Smartisan services to the HD2 Bluetooth and graphics hardware."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'disable-qadapter-and-restore-fast-icon-flip-v5'


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

    # Keep Smartisan's complete icon-face/edge/shadow flip timeline.  Its
    # original 400 ms pacing is too long for the single-core QSD8250 because a
    # cold app is also laying out underneath it.  Compress every tween by the
    # same factor to 220 ms, retaining the trajectory and reverse animation.
    flip = smali/'com/android/server/wm/SmartisanFlipAnimation.smali'
    code = flip.read_text()
    assert code.count('const/high16 v0, 0x43c80000    # 400.0f') == 1
    assert code.count('const-wide/16 v0, 0x190') == 1
    code = code.replace(
        'const/high16 v0, 0x43c80000    # 400.0f',
        'const v0, 0x435c0000    # 220.0f')
    code = code.replace('const-wide/16 v0, 0x190',
                        'const-wide/16 v0, 0xdc')

    # The donor converts the duration in seconds to long before multiplying by
    # 1000.  Any normal animation below one second therefore reports 0 ms to
    # WindowManager and is only ended by a 500 ms watchdog.  Convert after the
    # multiplication so the 220 ms timeline receives frames and completes by
    # its own callback.
    broken_duration = '''.method public getDuration()J
    .registers 5

    .prologue
    .line 376
    iget v0, p0, Lcom/android/server/wm/SmartisanFlipAnimation;->mRealDuration:F

    float-to-long v0, v0

    const-wide/16 v2, 0x3e8

    mul-long/2addr v0, v2

    return-wide v0
.end method'''
    fixed_duration = '''.method public getDuration()J
    .registers 3

    .prologue
    .line 376
    iget v0, p0, Lcom/android/server/wm/SmartisanFlipAnimation;->mRealDuration:F

    const/high16 v1, 0x447a0000    # 1000.0f

    mul-float/2addr v0, v1

    float-to-long v0, v0

    return-wide v0
.end method'''
    assert code.count(broken_duration) == 1
    code = code.replace(broken_duration, fixed_duration)

    # Correct the pre-animation projection too; the constructor still updates
    # these values from DisplayContent if rotation changes.
    assert code.count('const/16 v0, 0x438') == 1
    assert code.count('const/16 v0, 0x780') == 1
    code = code.replace('const/16 v0, 0x438', 'const/16 v0, 0x1e0')
    code = code.replace('const/16 v0, 0x780', 'const/16 v0, 0x320')
    code = code.replace('.field static final DURATION:J = 0x190L',
                        '.field static final DURATION:J = 0xdcL')
    flip.write_text(code)

    bg_alpha = smali/'com/android/server/wm/SmartisanFlipAnimation$BGAlphaAnimation.smali'
    code = bg_alpha.read_text()
    assert code.count('const-wide/16 v0, 0x190') == 1
    bg_alpha.write_text(code.replace('const-wide/16 v0, 0x190',
                                     'const-wide/16 v0, 0xdc'))

    # Retain a watchdog for broken app windows, but release touch 100 ms after
    # the expected end rather than holding the launcher for an extra 500 ms.
    transit_thread = smali/'com/android/server/wm/WindowManagerService$SmartisanTransitAnimThread.smali'
    code = transit_thread.read_text()
    assert code.count('add-int/lit16 v11, v0, 0x1f4') == 1
    transit_thread.write_text(code.replace(
        'add-int/lit16 v11, v0, 0x1f4',
        'add-int/lit8 v11, v0, 0x64'))

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
        'icon_flip_enabled': True,
        'icon_flip_duration_ms': 220,
        'icon_flip_timeout_ms': 320,
        'duration_conversion_fixed': True,
        'change': ('Keep the original signed Smartisan Bluetooth package and '
                   'do not bind its optional Qualcomm QAdapter service; retain '
                   'the complete forward/reverse icon-cell flip with an '
                   'HD2-paced 220 ms timeline.'),
    }
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
