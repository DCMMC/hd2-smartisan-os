#!/usr/bin/env python3
"""Complete the 720p texture set and fit launcher geometry to HD2 480x800.

The donor's 720p directory is incomplete, which made the launcher fall back to
its much heavier 1080p textures. Missing 720p files are generated from their
1080p counterparts at two-thirds size. Resource IDs and manifest stay intact.
This is a system-image APK patch; it is not an independently
installable/resigned APK.
"""
from pathlib import Path
import hashlib
import io
import json
import shutil
import struct
import subprocess
import zipfile
from PIL import Image
from launcher_resources import fit_hd2

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'hd2-480p-icon-atlas-and-full-fast-flip-v10'


def lean_unlock_xml(content):
    """Keep the staggered reveal while cutting per-cell work by about 3x."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(content)
    root.set('totalDuration', '0.12')
    root.set('totalFame', '10')
    for node in root:
        if node.tag == 'cell':
            index = int(node.get('index'))
            node.set('animcount', '1')
            node.set('init_alpha', '0.25f')
            node.set('init_scale', '0.97f')
            node.set('delay_frame', str(index % 2))
            for child in list(node):
                node.remove(child)
            ET.SubElement(node, 'pass', {
                'duration': '7', 'interpolator': 'CUBIC_OUT',
                'target_alpha': '0.0f', 'target_scale': '1.0f'})
        elif node.tag in ('statusbar', 'dock'):
            node.set('animcount', '1')
            node.set('init_alpha', '0.25f')
            node.set('init_scale', '0.97f')
            node.set('delay_frame', '0')
            for child in list(node):
                node.remove(child)
            ET.SubElement(node, 'pass', {
                'duration': '7', 'interpolator': 'CUBIC_OUT',
                'target_alpha': '0.0f', 'target_scale': '1.0f'})
        elif node.tag in ('batchshadow', 'background'):
            node.set('animcount', '1')
            node.set('delay_frame', '0')
            for child in list(node):
                node.remove(child)
            ET.SubElement(node, 'pass', {
                'duration': '7', 'interpolator': 'CUBIC_OUT',
                'target_alpha': '0.0f', 'target_scale': '1.0f'})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def patch_duration(content, old, new):
    import struct
    data = bytearray(content)
    needle = struct.pack('<I', old)
    hits = [i for i in range(len(data)-3) if data[i:i+4] == needle]
    assert len(hits) == 1, hits
    struct.pack_into('<I', data, hits[0], new)
    return bytes(data)


def patch_u32(content, old, new, expected=1):
    data = bytearray(content)
    needle = struct.pack('<I', old)
    hits = [i for i in range(len(data)-3) if data[i:i+4] == needle]
    assert len(hits) == expected, hits
    for offset in hits:
        struct.pack_into('<I', data, offset, new)
    return bytes(data)


def main():
    source = ROOT/'work/smartisan-donor/system/priv-app/LauncherSmartisanNew.apk'
    output = ROOT/'work/smartisan-compat/LauncherSmartisanNew.apk'
    report_path = ROOT/'logs/smartisan-launcher-patch.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    # Repacking the APK gives generated PNG entries new ZIP timestamps.  Reuse
    # an already verified artifact for this exact recipe and donor so image,
    # stage and live-device hashes remain reproducible.
    if output.exists() and report_path.exists():
        try:
            previous = json.loads(report_path.read_text())
            output_hash = hashlib.sha256(output.read_bytes()).hexdigest()
            if (previous.get('recipe') == RECIPE and
                    previous.get('source_sha256') == source_hash and
                    previous.get('output_sha256') == output_hash):
                print(output)
                return
        except (OSError, ValueError):
            pass
    smali = ROOT/'work/smartisan-launcher-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)
    log_class = smali/'com/smartisanos/launcher/LOG.smali'
    text = log_class.read_text()
    assert text.count('const-string v0, "ro.debuggable"') == 2
    text = text.replace(
        'const-string v0, "ro.debuggable"',
        'const-string v0, "persist.hd2.launcher_debug"',
    )
    noisy_error = '''.method private static _error(Ljava/lang/String;)V
    .registers 2
    .param p0, "info"    # Ljava/lang/String;

    .prologue
    .line 221
    const-string v0, "NewLauncher"

    invoke-static {v0, p0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    .line 222
    return-void
.end method'''
    quiet_error = '''.method private static _error(Ljava/lang/String;)V
    .registers 2
    .param p0, "info"    # Ljava/lang/String;

    sget-boolean v0, Lcom/smartisanos/launcher/LOG;->ENABLE_DEBUG:Z
    if-eqz v0, :done
    const-string v0, "NewLauncher"
    invoke-static {v0, p0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method'''
    assert text.count(noisy_error) == 1
    log_class.write_text(text.replace(noisy_error, quiet_error))

    # The keyguard sends a pre-dismiss notification, a hide notification and
    # USER_PRESENT for one gesture.  The stock receiver queues a complete GL
    # animation for every one, which is particularly visible on a single-core
    # HD2.  Ignore notifications received while the first unlock animation is
    # active; a later, independent unlock still passes this state gate.
    receiver = smali/'com/smartisanos/launcher/LauncherApplication$11.smali'
    code = receiver.read_text()
    dismiss_entry = '''    .line 440
    :cond_c7
    sget-boolean v4, Lcom/smartisanos/launcher/LOG;->ENABLE_DEBUG:Z'''
    debounced_entry = '''    .line 440
    :cond_c7
    invoke-static {}, Lcom/smartisanos/launcher/StatusManager;->getInstance()Lcom/smartisanos/launcher/StatusManager;
    move-result-object v4
    const/high16 v5, 0x80000
    invoke-virtual {v4, v5}, Lcom/smartisanos/launcher/StatusManager;->getLauncherStatus(I)Z
    move-result v4
    if-nez v4, :goto_12

    sget-boolean v4, Lcom/smartisanos/launcher/LOG;->ENABLE_DEBUG:Z'''
    assert code.count(dismiss_entry) == 1
    receiver.write_text(code.replace(dismiss_entry, debounced_entry, 1))

    # The keyguard-on broadcast can arrive before the launcher's GL page is
    # ready on this single-core device.  The stock code then leaves the unlock
    # animation uninitialised forever and every later swipe is ignored.  Retry
    # initialisation at the play boundary; the existing fallback still runs if
    # the page is genuinely unavailable.
    controller = smali/'com/smartisanos/launcher/AnimationController.smali'
    code = controller.read_text()
    unlock_gate = '''    iget-boolean v2, p0, Lcom/smartisanos/launcher/AnimationController;->mUnlockAnimationHasInit:Z

    if-nez v2, :cond_a1

    .line 905'''
    unlock_retry = '''    iget-boolean v2, p0, Lcom/smartisanos/launcher/AnimationController;->mUnlockAnimationHasInit:Z

    if-nez v2, :cond_a1

    # Boot-time keyguard notification may have preceded launcher page setup.
    invoke-virtual {p0, v4}, Lcom/smartisanos/launcher/AnimationController;->initUnlockAnimation(Z)V

    iget-boolean v2, p0, Lcom/smartisanos/launcher/AnimationController;->mUnlockAnimationHasInit:Z

    if-nez v2, :cond_a1

    .line 905'''
    assert code.count(unlock_gate) == 1
    controller.write_text(code.replace(unlock_gate, unlock_retry))

    # Smartisan renders the icon face, edge and shadow into a persistent atlas
    # shared with WindowManager.  The donor keeps a 384x1024 atlas even after
    # the launcher geometry has been fitted from 720x1280 to 480x800.  On the
    # HD2 that padded buffer consumes several MiB of the 32 MiB pmem arena and
    # fails to import into a cold-started app.  The fitted cell data observed
    # at runtime occupies 158x432, so 256x512 retains every texture region and
    # gives the legacy allocator power-of-two dimensions with much less waste.
    shooter = smali/'com/smartisanos/launcher/IconCellShoter.smali'
    code = shooter.read_text()
    assert code.count('const/16 v4, 0x180') == 2
    assert code.count('const/16 v4, 0x400') == 2
    code = code.replace('const/16 v4, 0x180', 'const/16 v4, 0x100')
    code = code.replace('const/16 v4, 0x400', 'const/16 v4, 0x200')
    # A failed GL event must not hold the system-server transition request for
    # the donor's 4500 ms.  Normal captures complete in about 50 ms on-device.
    assert code.count('const-wide/16 v8, 0x1194') == 1
    code = code.replace('const-wide/16 v8, 0x1194',
                        'const-wide/16 v8, 0x384')
    shooter.write_text(code)

    shot_event = smali/'com/smartisanos/launcher/IconCellShoter$1.smali'
    code = shot_event.read_text()
    assert code.count('const/16 v37, 0x180') == 1
    assert code.count('const/16 v38, 0x400') == 1
    code = code.replace('const/16 v37, 0x180', 'const/16 v37, 0x100')
    code = code.replace('const/16 v38, 0x400', 'const/16 v38, 0x200')
    shot_event.write_text(code)
    dex = ROOT/'work/smartisan-compat/LauncherSmartisanNew.dex'
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.smali.Main', 'assemble',
        '--jobs', '1', str(smali), '-o', str(dex),
    ], check=True)
    with zipfile.ZipFile(source) as archive:
        resources, resource_changes = fit_hd2(archive.read('resources.arsc'))
        prefix720 = 'assets/Textures/720p/'
        prefix1080 = 'assets/Textures/1080p/'
        paths720 = {e.filename[len(prefix720):] for e in archive.infolist()
                    if e.filename.startswith(prefix720) and not e.is_dir()}
        paths1080 = {e.filename[len(prefix1080):] for e in archive.infolist()
                     if e.filename.startswith(prefix1080) and not e.is_dir()}
        missing = sorted(paths1080-paths720)
        assert len(missing) == 163 and all(p.endswith('.png') for p in missing)
        generated = {}
        generated_pixels = 0
        source_pixels = 0
        for relative in missing:
            with Image.open(io.BytesIO(archive.read(prefix1080+relative))) as image:
                source_pixels += image.width*image.height
                size = (max(1, round(image.width*2/3)),
                        max(1, round(image.height*2/3)))
                resized = image.resize(size, Image.Resampling.LANCZOS)
                generated_pixels += size[0]*size[1]
                stream = io.BytesIO()
                resized.save(stream, 'PNG', optimize=True)
                generated[prefix720+relative] = stream.getvalue()
        # Launch only the incoming app layer.  Scaling the complete GL desktop
        # at the same time overloads the Adreno 200 composition path.
        app_enter = patch_duration(archive.read('res/anim/activity_up.xml'), 300, 95)
        # Move the incoming surface only 2% of the screen instead of 100%.
        # The animation remains visible without forcing a long full-panel move.
        app_enter = patch_u32(app_enter, 0x00000101, 0x028f5c31)
        app_exit = patch_duration(archive.read('res/anim/anim_fake.xml'), 350, 95)
        desktop_enter = patch_duration(
            archive.read('res/anim/wallpaper_open_enter.xml'), 400, 130)
        # Returning home keeps a subtle zoom, reducing 0.80 -> 1.0 to
        # 0.98 -> 1.0 so the GL desktop needs much less resampling.
        desktop_enter = patch_u32(desktop_enter, 0x3f4ccccd, 0x3f7ae148,
                                  expected=2)
        lean_unlock = {
            'assets/unlock9.xml': lean_unlock_xml(archive.read('assets/unlock9.xml')),
            'assets/unlock16.xml': lean_unlock_xml(archive.read('assets/unlock16.xml')),
        }
        with zipfile.ZipFile(output, 'w') as patched:
            for entry in archive.infolist():
                if entry.filename == 'resources.arsc':
                    content = resources
                elif entry.filename == 'classes.dex':
                    content = dex.read_bytes()
                elif entry.filename in ('res/anim/activity_up.xml',
                                         'res/anim/wallpaper_close_enter.xml'):
                    content = app_enter
                elif entry.filename in ('res/anim/anim_fake.xml',
                                         'res/anim/wallpaper_close_exit.xml'):
                    content = app_exit
                elif entry.filename == 'res/anim/wallpaper_open_enter.xml':
                    content = desktop_enter
                elif entry.filename in lean_unlock:
                    content = lean_unlock[entry.filename]
                else:
                    content = archive.read(entry.filename)
                patched.writestr(entry, content)
            for name, content in generated.items():
                patched.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
    report = {'recipe': RECIPE,
              'source_sha256': source_hash,
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'texture_path': '720p',
              'generated_720p_fallbacks': len(generated),
              'generated_pixel_ratio': generated_pixels/source_pixels,
              'debug_property': 'persist.hd2.launcher_debug',
              'boot_unlock_retry': True,
              'unlock_animation': 'debounced single-pass staggered reveal, 7 animation frames',
              'unlock_notification_debounce': True,
              'icon_flip_atlas': '256x512 (full face, edge and shadow regions)',
              'icon_capture_timeout_ms': 900,
              'app_open_animation': '95 ms 2-percent incoming slide without full-desktop scale',
              'change': ('Complete 720p textures from two-thirds-size 1080p '
                         'fallbacks; 480x800 geometry; keep the full Smartisan '
                         'icon flip in a pmem-safe 256x512 atlas; use lean '
                         'unlock and fallback app animations; make verbose '
                         'launcher logging opt-in instead of ro.debuggable'),
              'resource_changes': resource_changes}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__': main()
