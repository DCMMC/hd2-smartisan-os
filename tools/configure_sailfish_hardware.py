#!/usr/bin/env python3
"""HD2 audio, haptic and camera settings for the CM11/Sailfish adaptation."""
from pathlib import Path
import re


def configure_hardware(stage):
    changed = []
    relative = Path('etc/pulse/arm_droid_default.pa')
    target = stage/relative
    text = target.read_text()
    # HD2's primary output accepts 44100 Hz; the Xperia 48000 Hz request
    # makes audio.primary.qsd8k return -EINVAL and PulseAudio exit.
    text = re.sub(r'(?m)^(load-module module-droid-card .*\brate=)48000\b',
                  r'\g<1>44100', text)
    target.write_text(text)
    changed.append(relative)

    relative = Path('usr/share/ngfd/plugins.d/resource.ini')
    target = stage/relative
    text = re.sub(r'(?m)^(media\.vibra\s*=\s*)ffmemless\s*$',
                  r'\g<1>droid-vibrator', target.read_text())
    target.write_text(text)
    changed.append(relative)

    relative = Path('system/build.prop')
    target = stage/relative
    text = re.sub(r'(?m)^(?:persist.camera.shutter.disable=.*|# Sailfish owns camera sound feedback\.)\n?', '', target.read_text())
    # CameraService otherwise waits forever for AudioFlinger while loading
    # Android shutter samples. Native Sailfish feedback uses PulseAudio.
    text = text.rstrip()+'\n\n# Sailfish owns camera sound feedback.\npersist.camera.shutter.disable=1\n'
    target.write_text(text)
    changed.append(relative)
    return changed


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for relative in configure_hardware(root/'work/sailfish-stage'):
        print(relative)
