#!/usr/bin/env python3
"""Freeze the user-confirmed hardware state and integrate existing patches only."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from configure_sailfish_hardware import configure_hardware

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'work/sailfish-stage'
FOLDER = ROOT/'out/sailfish-alpha0/HD2-SF'
IMAGE = FOLDER/'rootfs.ext4'


def main():
    changed = configure_hardware(STAGE)
    changed.append(Path('lib/modules/2.6.32_tytung_jellybean_r2/kernel/drivers/net/wireless/bcm4329/bcm4329.ko'))
    status = json.loads((FOLDER/'BUILD-STATUS.json').read_text())
    status['status'] = 'alpha3: final snapshot for this session; experimental, hardware incomplete'
    status['user_confirmed'] = ['normal display', 'touch taps', 'swipe/unlock', 'sound', 'vibration']
    status['user_reported_not_working'] = ['Wi-Fi', 'camera']
    status['hardware_notes'] = {
        'audio': 'PulseAudio primary rate 48000 -> 44100; paplay succeeded; user confirms sound',
        'vibration': 'ngfd media.vibra maps to droid-vibrator; direct HAL test returned 0; user confirms vibration',
        'wifi': 'bcm4329 standard WEXT scan rejection removed; ConnMan enumerated 7 services; user still reports Wi-Fi not working',
        'camera': 'persist.camera.shutter.disable=1 removes CameraService AudioFlinger wait; preview buffer allocation still fails',
        'excluded_experiment': 'Temporary debug.composition.type=gpu did not fix preview and is not included in the image',
    }
    status['unresolved_risks'] = [
        'Wi-Fi not working for user despite successful scan enumeration',
        'Camera black preview: minisf gralloc -ENOMEM and BufferQueue dequeue errors',
        'Calls, cellular data, GPS, Bluetooth, sensors and suspend not validated',
        'Whole-process cgroup migration through tasks remains unverified',
        'Donor RPM metadata remains; no supported official OTA updates',
        'Repacked clean image not cold-boot tested; patches tested incrementally on the phone',
    ]
    status['known_unresolved'] = status['unresolved_risks']
    status['usb_debug']['root_rescue'] = 'USB RNDIS 192.168.2.15:2323 always on; systemd rescue also uses port 23'
    status['verified'] = [s for s in status.get('verified', []) if 'Wi-Fi' not in s]
    status['verified'] += ['User confirms physical swipe/unlock, sound and vibration',
                           'ConnMan scan returned services with patched bcm4329 module; connectivity remains broken']
    status['verified'] = list(dict.fromkeys(status['verified']))
    data = json.dumps(status, indent=2, ensure_ascii=False)+'\n'
    (FOLDER/'BUILD-STATUS.json').write_text(data)
    (STAGE/'etc/hd2-build-status.json').write_text(data)
    changed.append(Path('etc/hd2-build-status.json'))
    lines = []
    for relative in changed:
        source = STAGE/relative
        assert source.is_file() and not source.is_symlink(), source
        lines += [f'rm /{relative}', f'write {source} /{relative}',
                  f'sif /{relative} uid 0', f'sif /{relative} gid 0']
    commands = ROOT/'logs/sailfish-alpha3-image.commands'
    commands.write_text('\n'.join(lines)+'\n')
    with (ROOT/'logs/sailfish-alpha3-image.log').open('w') as log:
        subprocess.run(['debugfs', '-w', '-f', str(commands), str(IMAGE)], stdout=log, stderr=log, check=True)
    manifest = json.loads((ROOT/'logs/sailfish-patch-manifest.json').read_text())
    manifest['release'] = 'Sailfish 2.0.1.11 HD2 SD alpha3'
    by_path = {item['path']: item for item in manifest['files']}
    with tempfile.TemporaryDirectory() as temporary:
        for relative in changed:
            output = Path(temporary)/'dump'
            subprocess.run(['debugfs', '-R', f'dump /{relative} {output}', str(IMAGE)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            expected = hashlib.sha256((STAGE/relative).read_bytes()).hexdigest()
            assert hashlib.sha256(output.read_bytes()).hexdigest() == expected, relative
            output.unlink()
            by_path[str(relative)] = {'path': str(relative), 'sha256': expected, 'image_verified': True}
    manifest['files'] = [by_path[name] for name in sorted(by_path)]
    patch = 'configs/sailfish-bcm4329-wext-scan.patch'
    if patch not in manifest['kernel_patches']: manifest['kernel_patches'].append(patch)
    manifest['hardware'] = status['hardware_notes']
    manifest['limitations'] = status['unresolved_risks']
    manifest['runtime_evidence'] += ['User confirms physical swipe/unlock, audio and vibration',
                                   'Wi-Fi scanning partially improved; user reports Wi-Fi and camera still broken']
    manifest['runtime_evidence'] = list(dict.fromkeys(manifest['runtime_evidence']))
    manifest['wayland_lock_fix']['physical_swipe_retest_pending'] = False
    manifest['wayland_lock_fix']['physical_swipe_user_confirmed'] = True
    (ROOT/'logs/sailfish-patch-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (ROOT/'logs/sailfish-alpha3-hardware.json').write_text(json.dumps({
        'user_feedback': '声音和振动可以了，其他还是不行；停止修复，归档并发布',
        'image_files_verified': [str(p) for p in changed],
        'hardware': status['hardware_notes'], 'limitations': status['unresolved_risks'],
    }, indent=2, ensure_ascii=False)+'\n')
    current = json.loads((ROOT/'logs/CURRENT-STATUS.json').read_text())
    current.update({'active_work': 'Archive and publish final snapshots; hardware repair stopped at user request',
                    'sailfish_touch_verified': True,
                    'sailfish_lock_swipe_physical_retest_pending': False,
                    'sailfish_sound_user_confirmed': True, 'sailfish_vibration_user_confirmed': True,
                    'sailfish_wifi_user_reported_working': False, 'sailfish_camera_user_reported_working': False,
                    'sailfish_release_zip': 'out/hd2-sailfish-2.0.1.11-alpha3-SD.zip'})
    (ROOT/'logs/CURRENT-STATUS.json').write_text(json.dumps(current, indent=2)+'\n')
    print('Integrated and read-back verified', len(changed), 'existing patch files')


if __name__ == '__main__': main()
