#!/usr/bin/env python3
"""Build a separately named, HD2-compatible AOSP camera system app."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'aosp-camera2-clone-v1'


def main():
    source = ROOT/'work/hd2-base/system/app/Camera2.apk'
    output = ROOT/'work/smartisan-compat/HD2Camera.apk'
    key = ROOT/'configs/smartisan-compat/hd2-camera.keystore'
    report_path = ROOT/'logs/smartisan-hd2-camera-build.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists() and report_path.exists():
        previous = json.loads(report_path.read_text())
        if (previous.get('recipe') == RECIPE
                and previous.get('source_sha256') == source_hash
                and previous.get('output_sha256') == hashlib.sha256(output.read_bytes()).hexdigest()):
            print(output)
            return

    old_name = 'com.android.camera2'.encode('utf-16le')
    new_name = 'org.hd2port.camera2'.encode('utf-16le')
    assert len(old_name) == len(new_name)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, 'w') as new:
        for entry in old.infolist():
            if entry.filename.upper().startswith('META-INF/'):
                continue
            data = old.read(entry.filename)
            if entry.filename == 'AndroidManifest.xml':
                assert data.count(old_name) == 1
                data = data.replace(old_name, new_name)
            new.writestr(entry, data)
    subprocess.run([
        'jarsigner', '-keystore', str(key), '-storepass', 'hd2camera',
        '-keypass', 'hd2camera', '-sigalg', 'SHA1withRSA', '-digestalg', 'SHA1',
        str(output), 'hd2camera',
    ], check=True, stdout=subprocess.DEVNULL)
    report = {
        'recipe': RECIPE,
        'source_sha256': source_hash,
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'package': 'org.hd2port.camera2',
        'change': ('Clone the NexusHD2 AOSP Camera2 package under a unique name; '
                   'Smartisan Camera requests gralloc buffers unsupported by leo.'),
    }
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
