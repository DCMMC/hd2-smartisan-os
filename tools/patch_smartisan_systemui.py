#!/usr/bin/env python3
"""Fit Smartisan's fixed SystemUI resource geometry to the HD2.

Keep resource IDs, APK manifest and certificate entries unchanged, as with the
launcher system-image patch. This is not a normally installable signed update.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zipfile
from android_resources import scalar_entries, dimension

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'hd2-panel-geometry-and-lean-animation-v5'

# These dp values describe the full notification/control panel, not independent
# text or touch target sizes. The donor uses a 360x640 dp screen.
PANEL_DP = {
    'smartisan_status_bar_expanded_gradient_width',
    'smartisan_status_bar_expanded_gradient_height',
    'smartisan_status_bar_expanded_gradient_margin_top',
    'smartisan_status_bar_expanded_gradient_margin_left',
    'noti_panel_translate_y_threshold_for_toggle_recent_task',
    'noti_panel_translate_y_threshold_for_switch',
    'music_view_margin_top', 'music_info_margin_top',
    'power_widget_height', 'power_widget_width',
    'smartisan_notifications_clear_button_translate_y',
}


def fit_hd2(original):
    data = bytearray(original)
    changes = []
    for entry in scalar_entries(data):
        if entry['type'] != 'dimen' or entry['data_type'] != 5:
            continue
        name, density = entry['name'], entry['density']
        unit, old = entry['value'] & 15, dimension(entry['value'])
        landscape = entry['orientation'] == 2
        if unit == 0 and density in (320, 480):
            source_scale = density / 320
        elif unit == 1 and name in PANEL_DP:
            source_scale = 0.5  # dp -> donor xhdpi pixels
        else:
            continue
        # Preserve the current framework's 52px status bar. Scale panel height
        # to the remaining usable area, rather than overflowing below the LCD.
        xratio = (800 / 1280 if landscape else 480 / 720) / source_scale
        yratio = ((480-52)/(720-52) if landscape else (800-52)/(1280-52)) / source_scale
        vertical = bool(re.search(r'height|margin_top|margin_bottom|padding_top|padding_bottom|translate_y|_y_position|_y_transition|screen_y_position|y_threshold', name))
        new = round(old * (yratio if vertical else xratio))
        if name == 'screen_port_height':
            new = 800
        if old and not new:
            new = 1 if old > 0 else -1
        # Encode integer pixels (radix 0, unit px), with signed 24-bit mantissa.
        assert -0x800000 <= new < 0x800000
        value = (new << 8) & 0xffffff00
        if value != entry['value']:
            struct.pack_into('<I', data, entry['offset'], value)
            changes.append({'name': name, 'density': density,
                            'orientation': entry['orientation'],
                            'from': old, 'from_unit': unit, 'to_px': new})
    assert len([r for r in changes if r['name'] == 'power_widget_width']) == 2
    assert len([r for r in changes if r['name'] == 'smartisan_notifications_container_width']) == 4
    return data, changes


def main():
    source = ROOT/'work/smartisan-donor/system/priv-app/SystemUISmartisan.apk'
    output = ROOT/'work/smartisan-compat/SystemUISmartisan.apk'
    smali = ROOT/'work/smartisan-systemui-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)

    # The userdebug base keeps ro.debuggable=1 so ADB remains root-capable, but
    # Smartisan also uses that flag to enable its very noisy UI logger. Keep an
    # explicit opt-in property for debugging without writing logs every frame.
    logger = smali/'com/smartisanos/systemui/b/q.smali'
    text = logger.read_text()
    debug_property = '    const-string v2, "ro.debuggable"'
    assert text.count(debug_property) == 1
    logger.write_text(text.replace(
        debug_property,
        '    const-string v2, "persist.hd2.systemui_debug"',
    ))

    # Preserve Smartisan's hardware-layer lifecycle, which is the most stable
    # path on the old Adreno driver. Shorten the dead delay before it starts and
    # finish all three translations together in 240 ms, retaining a visible
    # transition without stretching missed frames over a long animation.
    switch = smali/'com/smartisanos/systemui/s.smali'
    text = switch.read_text()
    replacements = {
        '    const-wide/16 v2, 0x32': ('    const-wide/16 v2, 0x10', 2),
        '    const-wide/16 v11, 0xc8': ('    const-wide/16 v11, 0x78', 1),
        '    const-wide/16 v4, 0x12c': ('    const-wide/16 v4, 0xf0', 2),
        '    const-wide/16 v11, 0x12c': ('    const-wide/16 v11, 0xf0', 1),
    }
    timing_changes = {}
    for old, (new, expected) in replacements.items():
        count = text.count(old)
        assert count == expected, (old, count)
        text = text.replace(old, new)
        timing_changes[old.strip()] = {'replacement': new.strip(), 'count': count}
    switch.write_text(text)

    dex = ROOT/'work/smartisan-compat/SystemUISmartisan.dex'
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.smali.Main', 'assemble',
        '--jobs', '1', str(smali), '-o', str(dex),
    ], check=True)
    with zipfile.ZipFile(source) as archive:
        data, changes = fit_hd2(archive.read('resources.arsc'))
        with zipfile.ZipFile(output, 'w') as patched:
            for entry in archive.infolist():
                if entry.filename == 'resources.arsc':
                    content = data
                elif entry.filename == 'classes.dex':
                    content = dex.read_bytes()
                else:
                    content = archive.read(entry.filename)
                patched.writestr(entry, content)
    report = {'recipe': RECIPE,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'resource_changes': changes,
              'systemui_debug_property': 'persist.hd2.systemui_debug',
              'timing_changes': timing_changes,
              'animation_layer_policy': (
                  'retain the stock short-lived hardware layers and release them '
                  'at animation end; use a 16 ms start delay and 240 ms motion')}
    (ROOT/'logs/smartisan-systemui-patch.json').write_text(json.dumps(report, indent=2)+'\n')
    print(output, len(changes), 'resource changes')


if __name__ == '__main__':
    main()
