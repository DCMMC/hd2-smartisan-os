#!/usr/bin/env python3
"""Fit the Smartisan keyguard to 480x800 and quiet its hot-path logging."""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import zipfile

from android_resources import scalar_entries, dimension

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'hd2-keyguard-480x800-opaque-fast-reliable-unlock-v5'


LOGGER = r'''.class public final Lcom/smartisanos/keyguard/Hd2Log;
.super Ljava/lang/Object;

.field private static final ENABLED:Z

.method static constructor <clinit>()V
    .registers 2
    const-string v0, "persist.hd2.keyguard_debug"
    const/4 v1, 0x0
    invoke-static {v0, v1}, Landroid/os/SystemProperties;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0
    sput-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    return-void
.end method

.method public static v(Ljava/lang/String;Ljava/lang/String;)I
    .registers 3
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1}, Landroid/util/Log;->v(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static d(Ljava/lang/String;Ljava/lang/String;)I
    .registers 3
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static i(Ljava/lang/String;Ljava/lang/String;)I
    .registers 3
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static w(Ljava/lang/String;Ljava/lang/String;)I
    .registers 3
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    .registers 4
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1, p2}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static e(Ljava/lang/String;Ljava/lang/String;)I
    .registers 3
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method

.method public static e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    .registers 4
    sget-boolean v0, Lcom/smartisanos/keyguard/Hd2Log;->ENABLED:Z
    if-eqz v0, :quiet
    invoke-static {p0, p1, p2}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    move-result v0
    return v0
    :quiet
    const/4 v0, 0x0
    return v0
.end method
'''


# Values are physical pixels.  The donor xxhdpi table is 1080x1920; Android
# selects it even on the HD2 because it is the only density-qualified table.
TARGET_DIMENSIONS = {
    'keyguard_screen_port_height': 800,
    'keyguard_screen_port_width': 480,
    'keyguard_charging_padding_bottom': 78,
    'keyguard_slide_bar_offset': 62,
    'keyguard_slide_bar_height': 66,
    'keyguard_slide_trigger_offset': 495,
    'keyguard_unlock_area_height': -83,
    'keyguard_unlock_area_height_view': 3,
    'keyguard_ignore_move_offset': 12,
    'keyguard_scroll_start_offset': 833,
    'keyguard_security_view_offset': 869,
    'keyguard_dismiss_status_bar_offset': 792,
    'keyguard_dismiss_status_bar_offset_camera': 788,
    'keyguard_dismiss_status_bar_offset_final': 813,
    'keyguard_album_image_size': 141,
    'keyguard_slidebar_icon_border': 13,
    'keyguard_recorder_waveview_width': 228,
}


def complex_px(value):
    return ((value & 0xffffff) << 8) & 0xffffffff


def patch_resources(content):
    data = bytearray(content)
    changes = []
    for entry in scalar_entries(data):
        if entry['type'] != 'dimen' or entry['name'] not in TARGET_DIMENSIONS:
            continue
        assert entry['data_type'] == 5 and entry['value'] & 0xff == 0
        old = entry['value'] >> 8
        if old & 0x800000:
            old -= 0x1000000
        new = TARGET_DIMENSIONS[entry['name']]
        struct.pack_into('<I', data, entry['offset'], complex_px(new))
        changes.append({'name': entry['name'], 'density': entry['density'],
                        'from': old, 'to': new})
    assert len(changes) == len(TARGET_DIMENSIONS) * 2, len(changes)
    return bytes(data), changes


def _string_pool(data, pos):
    """Return the strings and size of a binary Android string pool."""
    kind, header, size, count, styles, flags, start, unused = \
        struct.unpack_from('<HH6I', data, pos)
    assert kind == 1

    def short_length(offset):
        value = data[offset]
        if value & 0x80:
            return ((value & 0x7f) << 8) | data[offset + 1], offset + 2
        return value, offset + 1

    strings = []
    for index in range(count):
        offset = pos + start + struct.unpack_from(
            '<I', data, pos + header + 4 * index)[0]
        if flags & 0x100:
            _, offset = short_length(offset)
            length, offset = short_length(offset)
            strings.append(bytes(data[offset:offset + length]).decode('utf-8'))
        else:
            length = struct.unpack_from('<H', data, offset)[0]
            if length & 0x8000:
                length = ((length & 0x7fff) << 16) | struct.unpack_from(
                    '<H', data, offset + 2)[0]
                offset += 4
            else:
                offset += 2
            strings.append(bytes(data[offset:offset + 2 * length]).decode('utf-16le'))
    return strings, size


def patch_layout(content, name):
    """Scale literal xxhdpi pixel coordinates to the HD2 panel.

    These old layouts use px literals instead of dp/resources, so Android's
    density selection leaves a 1080x1920 tree on a 480x800 framebuffer.
    """
    data = bytearray(content)
    strings, pool_size = _string_pool(data, 8)
    pos = 8 + pool_size
    if struct.unpack_from('<H', data, pos)[0] == 0x180:
        pos += struct.unpack_from('<I', data, pos + 4)[0]
    changes = []
    while pos < len(data):
        kind, header, size = struct.unpack_from('<HHI', data, pos)
        if kind == 0x102:  # RES_XML_START_ELEMENT_TYPE
            fields = struct.unpack_from('<4I6H', data, pos + 8)
            attribute_start, attribute_size, attribute_count = fields[4:7]
            attrs = pos + 16 + attribute_start
            for index in range(attribute_count):
                attr = attrs + index * attribute_size
                attr_name = strings[struct.unpack_from('<I', data, attr + 4)[0]]
                value_type = data[attr + 15]
                value = struct.unpack_from('<I', data, attr + 16)[0]
                if value_type != 5 or value & 0xf:  # only literal integer px
                    continue
                old = dimension(value)
                vertical = any(token in attr_name for token in (
                    'height', 'Top', 'Bottom', 'paddingTop', 'paddingBottom',
                    'lineSpacing'))
                # These two host layouts position several children from the
                # top of the 1920 px content *after* applying a 78 px status
                # bar inset.  Scaling each value independently left their
                # bottom bar 23 px below the HD2 panel.  Keep their absolute
                # screen edges aligned instead.
                host_vertical = {
                    846: 333,
                    1628: 659,
                    1695: 683,
                    1836: 737,
                    1841: 748,
                }
                is_host = name.endswith(('keyguard_host_view.xml',
                                         'keyguard_host_view_left_mode.xml'))
                if vertical and is_host and old in host_vertical:
                    new = host_vertical[old]
                elif vertical and old == 78:
                    new = 52  # match the HD2 framework status bar exactly
                elif vertical and old in (1920, 2070):
                    new = 800
                elif vertical and old == 1705:
                    new = 710
                else:
                    ratio = 800 / 1920 if vertical else 480 / 1080
                    new = round(old * ratio)
                if old and not new:
                    new = 1 if old > 0 else -1
                if new == old:
                    continue
                struct.pack_into('<I', data, attr + 16, complex_px(new))
                changes.append({'layout': name, 'attribute': attr_name,
                                'from': old, 'to': new})
        pos += size
    return bytes(data), changes


def main():
    source = ROOT/'work/smartisan-donor/system/priv-app/KeyguardSmartisan.apk'
    output = ROOT/'work/smartisan-compat/KeyguardSmartisan.apk'
    smali = ROOT/'work/smartisan-keyguard-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)

    log_calls = 0
    for path in smali.rglob('*.smali'):
        text = path.read_text()
        count = text.count('Landroid/util/Log;->')
        if count:
            path.write_text(text.replace('Landroid/util/Log;->',
                                         'Lcom/smartisanos/keyguard/Hd2Log;->'))
            log_calls += count
    assert log_calls == 263, log_calls
    (smali/'com/smartisanos/keyguard/Hd2Log.smali').write_text(LOGGER)

    host = smali/'com/smartisanos/keyguard/KeyguardHostView.smali'
    text = host.read_text()
    # 78 px is the donor status-bar height; 1705 px is its lower desk bar.
    assert text.count('const/high16 v2, -0x3d640000    # -78.0f') == 1
    assert text.count('const/16 v2, 0x6a9') == 1
    text = text.replace('const/high16 v2, -0x3d640000    # -78.0f',
                        'const/high16 v2, -0x3db00000    # -52.0f')
    text = text.replace('const/16 v2, 0x6a9', 'const/16 v2, 0x2c6')
    # Keep the slide animation visible but finish it in roughly 120 ms rather
    # than spending more than 600 ms scrolling a full-screen software tree.
    assert text.count('mul-int/lit16 v0, p2, 0x1f4') == 1
    text = text.replace('mul-int/lit16 v0, p2, 0x1f4',
                        'mul-int/lit8 v0, p2, 0x18')
    # Camera-side slide coordinates use the donor panel height directly.
    assert text.count('const/16 v2, 0x780') == 1
    text = text.replace('const/16 v2, 0x780', 'const/16 v2, 0x320')
    text = text.replace('const/16 v4, -0x9c4', 'const/16 v4, -0x412')
    text = text.replace('const/16 v5, 0x4b0', 'const/16 v5, 0x15e')
    # Smartisan normally marks the keyguard as dismissable and waits for its
    # launcher GL animation to drive the final transition.  On the HD2 the GL
    # thread can be throttled while the keyguard surface is on top, leaving a
    # fully scrolled-away keyguard that still owns input forever.  Complete the
    # normal mediator path after the short slide.  aU() retains the stock
    # security-mode checks, so PIN/pattern/password screens are not bypassed.
    assert text.count('const-wide/16 v2, 0x276') == 1
    assert text.count('const-wide/16 v2, 0x320') >= 2
    text = text.replace('const-wide/16 v2, 0x276',
                        'const-wide/16 v2, 0xf0', 1)  # 630 -> 240 ms
    # The first 800 ms occurrence belongs to the alternate snap-to-top path.
    text = text.replace('const-wide/16 v2, 0x320',
                        'const-wide/16 v2, 0x104', 1)  # 800 -> 260 ms

    # app_capature is a full-screen snapshot used by the unlock transition.
    # On the donor panel its alpha mask is initialised later, but on the HD2 a
    # transparent band can expose the previously open application at rest.
    # Initialise the existing full-screen alpha_layer to opaque black.  It is
    # behind the lockscreen content and the stock drag code still fades it.
    alpha_assignment = '''    iput-object v1, v0, Lcom/smartisanos/keyguard/KeyguardHostView;->bp:Landroid/widget/ImageView;

    .line 2768'''
    alpha_initialised = '''    iput-object v1, v0, Lcom/smartisanos/keyguard/KeyguardHostView;->bp:Landroid/widget/ImageView;

    move-object/from16 v0, p0
    invoke-direct {v0}, Lcom/smartisanos/keyguard/KeyguardHostView;->av()V

    .line 2768'''
    assert text.count(alpha_assignment) == 1
    text = text.replace(alpha_assignment, alpha_initialised, 1)
    host.write_text(text)

    unlock_callbacks = 0
    callback_needle = '''    invoke-interface {v0}, Lcom/smartisanos/keyguard/KeyguardViewMediator$ViewMediatorCallback;->cG()V

    .line '''
    callback_replacement = '''    invoke-interface {v0}, Lcom/smartisanos/keyguard/KeyguardViewMediator$ViewMediatorCallback;->cG()V

    # Reliably finish the stock mediator transition after the visual slide.
    iget-object v0, p0, Lcom/smartisanos/keyguard/CLASS_NAME;->aw:Lcom/smartisanos/keyguard/KeyguardHostView;
    invoke-virtual {v0}, Lcom/smartisanos/keyguard/KeyguardHostView;->aU()V

    .line '''
    for klass in ('G', 'O'):
        path = smali/f'com/smartisanos/keyguard/{klass}.smali'
        code = path.read_text()
        assert code.count(callback_needle) == 1, klass
        code = code.replace(callback_needle,
                            callback_replacement.replace('CLASS_NAME', klass), 1)
        path.write_text(code)
        unlock_callbacks += 1

    # The keyguard's bitmap path bypasses resources and explicitly allocates
    # 1080x1705 wallpapers.  Keeping those textures causes repeated GL 0x501
    # failures and stalls on Adreno 200, so generate only the visible HD2 area.
    geometry_replacements = {
        'const/16 v0, 0x438': 'const/16 v0, 0x1e0',
        'const/16 v1, 0x438': 'const/16 v1, 0x1e0',
        'const/16 v2, 0x438': 'const/16 v2, 0x1e0',
        'const/16 v3, 0x438': 'const/16 v3, 0x1e0',
        'const/16 v4, 0x438': 'const/16 v4, 0x1e0',
        'const/16 v5, 0x438': 'const/16 v5, 0x1e0',
        'const/16 v6, 0x438': 'const/16 v6, 0x1e0',
        'const/16 v0, 0x6a9': 'const/16 v0, 0x2c6',
        'const/16 v1, 0x6a9': 'const/16 v1, 0x2c6',
        'const/16 v2, 0x6a9': 'const/16 v2, 0x2c6',
        'const/16 v3, 0x6a9': 'const/16 v3, 0x2c6',
        'const/16 v4, 0x6a9': 'const/16 v4, 0x2c6',
        'const/16 v5, 0x6a9': 'const/16 v5, 0x2c6',
        'const/16 v6, 0x6a9': 'const/16 v6, 0x2c6',
        # Header and lower-bar crops within the 1705 px wallpaper.
        'const/16 v0, 0x4e': 'const/16 v0, 0x34',
        'const/16 v1, 0x4e': 'const/16 v1, 0x34',
        'const/16 v2, 0x4e': 'const/16 v2, 0x34',
        'const/16 v3, 0x4e': 'const/16 v3, 0x34',
        'const/16 v4, 0x4e': 'const/16 v4, 0x34',
        'const/16 v5, 0x4e': 'const/16 v5, 0x34',
        'const/16 v6, 0x4e': 'const/16 v6, 0x34',
        'const/16 v0, 0x5fb': 'const/16 v0, 0x27e',
        'const/16 v1, 0x5fb': 'const/16 v1, 0x27e',
        'const/16 v2, 0x5fb': 'const/16 v2, 0x27e',
        'const/16 v3, 0x5fb': 'const/16 v3, 0x27e',
        'const/16 v4, 0x5fb': 'const/16 v4, 0x27e',
        'const/16 v5, 0x5fb': 'const/16 v5, 0x27e',
        'const/16 v6, 0x5fb': 'const/16 v6, 0x27e',
        'const/16 v0, 0xae': 'const/16 v0, 0x48',
        'const/16 v1, 0xae': 'const/16 v1, 0x48',
        'const/16 v2, 0xae': 'const/16 v2, 0x48',
        'const/16 v3, 0xae': 'const/16 v3, 0x48',
        'const/16 v4, 0xae': 'const/16 v4, 0x48',
        'const/16 v5, 0xae': 'const/16 v5, 0x48',
        'const/16 v6, 0xae': 'const/16 v6, 0x48',
    }
    geometry_counts = {}
    for relative in (
            'com/smartisanos/keyguard/KeyguardBitmapData.smali',
            'com/smartisanos/utils/BitmapGaussianBlur.smali'):
        path = smali/relative
        code = path.read_text()
        count = 0
        for old, new in geometry_replacements.items():
            hits = code.count(old)
            if hits:
                code = code.replace(old, new)
                count += hits
        assert count, relative
        path.write_text(code)
        geometry_counts[relative] = count

    pager = smali/'com/smartisanos/keyguard/widgets/KeyguardViewPager.smali'
    code = pager.read_text()
    pager_count = code.count('const/16 v0, 0x438') + \
        code.count('const/16 v1, 0x438') + \
        code.count('const/high16 v5, 0x44870000    # 1080.0f')
    assert pager_count == 5, pager_count
    code = code.replace('const/16 v0, 0x438', 'const/16 v0, 0x1e0')
    code = code.replace('const/16 v1, 0x438', 'const/16 v1, 0x1e0')
    code = code.replace('const/high16 v5, 0x44870000    # 1080.0f',
                        'const/high16 v5, 0x43f00000    # 480.0f')
    pager.write_text(code)

    pager_state = smali/'com/smartisanos/keyguard/widgets/s.smali'
    code = pager_state.read_text()
    assert code.count('const/16 v0, 0x438') == 1
    pager_state.write_text(code.replace('const/16 v0, 0x438',
                                        'const/16 v0, 0x1e0'))

    quick = smali/'com/smartisanos/keyguard/widgets/QuickLaunchPickerView.smali'
    code = quick.read_text()
    assert code.count('const/16 v0, 0x438') == 1
    assert code.count('const/16 v0, 0x780') == 1
    code = code.replace('const/16 v0, 0x438', 'const/16 v0, 0x1e0')
    code = code.replace('const/16 v0, 0x780', 'const/16 v0, 0x320')
    code = code.replace('const/16 v0, 0x466', 'const/16 v0, 0x1f4')
    quick.write_text(code)

    dex = ROOT/'work/smartisan-compat/KeyguardSmartisan.dex'
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.smali.Main', 'assemble',
        '--jobs', '1', str(smali), '-o', str(dex),
    ], check=True)
    with zipfile.ZipFile(source) as archive:
        resources, changes = patch_resources(archive.read('resources.arsc'))
        layout_changes = []
        with zipfile.ZipFile(output, 'w') as patched:
            for entry in archive.infolist():
                if entry.filename == 'classes.dex':
                    content = dex.read_bytes()
                elif entry.filename == 'resources.arsc':
                    content = resources
                elif entry.filename.startswith('res/layout-xxhdpi/') and \
                        entry.filename.endswith('.xml'):
                    content, entry_changes = patch_layout(
                        archive.read(entry.filename), entry.filename)
                    layout_changes.extend(entry_changes)
                else:
                    content = archive.read(entry.filename)
                patched.writestr(entry, content)

    report = {
        'recipe': RECIPE,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'screen': '480x800',
        'status_bar_height': 52,
        'bottom_bar_y': 710,
        'layout_pixel_changes': len(layout_changes),
        'wallpaper_texture': '480x710',
        'slide_animation': 'approximately 120 ms',
        'unlock_completion_delay_ms': [240, 260],
        'opaque_capture_mask_at_rest': True,
        'security_aware_unlock_callbacks': unlock_callbacks,
        'geometry_smali_changes': geometry_counts,
        'redirected_log_calls': log_calls,
        'debug_property': 'persist.hd2.keyguard_debug',
        'resource_changes': changes,
    }
    (ROOT/'logs/smartisan-keyguard-patch.json').write_text(
        json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
