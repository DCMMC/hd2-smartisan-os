#!/usr/bin/env python3
"""Reproduce hardware bring-up patches in the stage, SD image and ramdisk."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from configure_debug import configure_smartisan_ramdisk
from firmware import unpack_cpio, pack_cpio

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'work/smartisan-stage'
BOOT = ROOT / 'out/smartisan-alpha0/HD2-SM20'


def integrate(update_image=False):
    for script in ['build_smartisan_compat.py', 'patch_vector_abi.py',
                   'patch_gralloc_abi.py', 'patch_smartisan_platform.py', 'patch_smartisan_launcher.py',
                   'patch_smartisan_camera.py', 'patch_smartisan_core.py',
                   'patch_smartisan_hwui.py', 'patch_smartisan_systemui.py']:
        subprocess.run([sys.executable, str(ROOT/'tools'/script)], check=True)
    mapping = {f'system/lib/{name}': ROOT/'work/smartisan-compat'/name
               for name in ['libhd2compat.so', 'libutils.so', 'libui.so',
                            'libcutils.so', 'libsurfaceflinger.so', 'libcamera.so',
                            'libhwui.so']}
    mapping['system/lib/egl/eglsubAndroid.so'] = ROOT/'work/smartisan-compat/eglsubAndroid.so'
    mapping['system/bin/app_process.hd2'] = ROOT/'work/smartisan-donor/system/bin/app_process'
    mapping['system/bin/app_process'] = ROOT/'configs/smartisan-compat/app_process'
    mapping['system/bin/hd2-runtime'] = ROOT/'configs/smartisan-compat/hd2-runtime'
    mapping['system/priv-app/LauncherSmartisanNew.apk'] = ROOT/'work/smartisan-compat/LauncherSmartisanNew.apk'
    mapping['system/priv-app/SystemUISmartisan.apk'] = ROOT/'work/smartisan-compat/SystemUISmartisan.apk'
    mapping['system/framework/core.jar'] = ROOT/'work/smartisan-compat/core.jar'
    for name, source in mapping.items():
        shutil.copyfile(source, STAGE/name)
        (STAGE/name).chmod(0o755 if name.startswith('system/bin/') else 0o644)
    props = STAGE/'system/build.prop'
    overrides = {'debug.gr.numframebuffers': '3',
                 'dalvik.vm.jit.codecachesize': '1024',
                 'persist.sys.force_highendgfx': '0'}
    lines = [s for s in props.read_text().splitlines()
             if s.partition('=')[0] not in overrides]
    props.write_text('\n'.join(lines)+'\n'+''.join(k+'='+v+'\n' for k,v in overrides.items()))
    mapping['system/build.prop'] = props
    # The old RPC server thread is detached, yet teardown tries to join it and
    # frees its transport while it may still traverse the server list. Use the
    # GPS driver's existing keep-initialized option; gps_start/gps_stop remain.
    gps = STAGE/'system/etc/gps.conf'
    lines = [s for s in gps.read_text().splitlines()
             if not s.startswith('GPS1_CLEANUP_ENABLED=')]
    gps.write_text('\n'.join(lines)+'\nGPS1_CLEANUP_ENABLED=0\n')
    mapping['system/etc/gps.conf'] = gps
    # No NFC controller or p2p_supplicant exists in this HD2 HAL/firmware set.
    removed = ['system/app/NfcNci.apk', 'system/app/TimeService.apk',
               'system/app/qcrilmsgtunnel.apk'] + ['system/etc/permissions/'+name for name in
               ['android.hardware.nfc.hce.xml', 'android.hardware.nfc.xml',
                'com.android.nfc_extras.xml', 'com.broadcom.nfc.xml', 'com.vzw.nfc.xml',
                'android.hardware.wifi.direct.xml']]
    for name in removed:
        (STAGE/name).unlink(missing_ok=True)
    ramdisk = BOOT/'initrd.gz'
    ramdisk.write_bytes(pack_cpio(configure_smartisan_ramdisk(unpack_cpio(ramdisk.read_bytes()))))
    if update_image:
        image = BOOT/'rootfs.ext4'
        backup = ROOT/'backups/smartisan-before-runtime-compat.ext4'
        if not backup.exists():
            subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(image), str(backup)], check=True)
        commands = []
        for name in mapping:
            path = STAGE/name
            commands += [f'rm /{name}', f'write {path} /{name}',
                         f'set_inode_field /{name} mode 0100{755 if name.startswith("system/bin/") else 644}',
                         f'set_inode_field /{name} uid 0',
                         f'set_inode_field /{name} gid {2000 if name.startswith("system/bin/") else 0}']
        commands += [f'rm /{name}' for name in removed]
        command_file = ROOT/'work/smartisan-compat/update-image.debugfs'
        command_file.write_text('\n'.join(commands)+'\n')
        result = subprocess.run(['debugfs', '-w', '-f', str(command_file), str(image)],
                                capture_output=True, text=True, check=True)
        (ROOT/'logs/smartisan-integrate-debugfs.log').write_text(result.stdout+result.stderr)
        subprocess.run(['e2fsck', '-fn', str(image)], check=True)
    report = {'files': {name: hashlib.sha256((STAGE/name).read_bytes()).hexdigest() for name in mapping},
              'removed': removed, 'local_image_updated': update_image,
              'device_evidence': 'root ADB, SurfaceFlinger, Zygote, system_server, launcher process, boot-complete',
              'user_evidence': 'Desktop dimensions confirmed correct; quick-controls layout and severe lag reported next',
              'not_verified': ['acceptable interaction latency', 'calls', 'Wi-Fi', 'audio', 'camera']}
    (ROOT/'logs/smartisan-compat-manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return mapping


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-image', action='store_true')
    integrate(parser.parse_args().update_image)
