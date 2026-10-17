#!/usr/bin/env python3
"""Make the HD2 power key and Smartisan global-actions path reliable."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'hd2-power-key-global-actions-v1'


def main():
    source = ROOT/'work/smartisan-donor/system/framework/android.policy.jar'
    output = ROOT/'work/smartisan-compat/android.policy.jar'
    smali = ROOT/'work/smartisan-policy-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)

    policy = smali/'com/android/internal/policy/impl/PhoneWindowManager.smali'
    code = policy.read_text()
    # The donor waits 1.5 s and then waits another 500 ms before displaying.
    assert code.count('const-wide/16 v2, 0x5dc') == 1
    code = code.replace('const-wide/16 v2, 0x5dc',
                        'const-wide/16 v2, 0x320')
    policy.write_text(code)

    runnable = smali/'com/android/internal/policy/impl/PhoneWindowManager$37.smali'
    code = runnable.read_text()
    assert code.count('const-wide/16 v3, 0x1f4') == 1
    runnable.write_text(code.replace('const-wide/16 v3, 0x1f4',
                                     'const-wide/16 v3, 0x64'))

    # SurfaceControl.screenshot() can return null with the legacy genlock
    # stack.  The stock listener dereferences it and kills system_server.
    listener = smali/'com/android/internal/policy/impl/SmartisanGlobalActions$6.smali'
    code = listener.read_text()
    needle = '''    move-result-object v0

    invoke-virtual {v0}, Landroid/graphics/Bitmap;->prepareToDraw()V

    .line 379'''
    replacement = '''    move-result-object v0

    if-eqz v0, :goto_c

    invoke-virtual {v0}, Landroid/graphics/Bitmap;->prepareToDraw()V

    .line 379'''
    assert code.count(needle) == 1
    listener.write_text(code.replace(needle, replacement))

    dex = ROOT/'work/smartisan-compat/android.policy.dex'
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.smali.Main', 'assemble',
        '--jobs', '1', str(smali), '-o', str(dex),
    ], check=True)
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(output, 'w') as patched:
        for entry in archive.infolist():
            content = dex.read_bytes() if entry.filename == 'classes.dex' \
                else archive.read(entry.filename)
            patched.writestr(entry, content)

    report = {
        'recipe': RECIPE,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'long_press_delay_ms': 800,
        'menu_show_delay_ms': 100,
        'null_screenshot_guard': True,
    }
    (ROOT/'logs/smartisan-policy-patch.json').write_text(
        json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
