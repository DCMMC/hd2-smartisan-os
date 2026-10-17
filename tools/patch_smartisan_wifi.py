#!/usr/bin/env python3
"""Use the HD2 wpa_supplicant's single-interface control protocol."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'wifi-native-single-interface-v4'


def main():
    source = ROOT/'work/smartisan-donor/system/framework/framework.jar'
    output = ROOT/'work/smartisan-compat/framework.jar'
    report_path = ROOT/'logs/smartisan-wifi-framework-patch.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists() and report_path.exists():
        previous = json.loads(report_path.read_text())
        if (
            previous.get('recipe') == RECIPE
            and previous.get('source_sha256') == source_hash
            and previous.get('output_sha256') == hashlib.sha256(output.read_bytes()).hexdigest()
        ):
            print(output)
            return

    smali = ROOT/'work/smartisan-wifi-framework-smali'
    if smali.exists():
        shutil.rmtree(smali)
    classpath = str(ROOT/'sources/smali-jars/*')
    subprocess.run([
        'java', '-cp', classpath, 'org.jf.baksmali.Main', 'disassemble',
        '--jobs', '1', '-o', str(smali), str(source),
    ], check=True)
    native = smali/'android/net/wifi/WifiNative.smali'
    text = native.read_text()
    before = '    if-nez v0, :cond_42'
    assert text.count(before) == 1
    text = text.replace(before, '    goto :cond_42')

    # leo's old supplicant exposes BSS RANGE only once after a scan; later
    # reads are empty while SCAN_RESULTS remains valid. Convert its stable
    # tabular response to the key/value format parsed by WifiStateMachine.
    scan_method = re.compile(
        r'\.method public scanResults\(I\)Ljava/lang/String;.*?^\.end method$',
        re.MULTILINE | re.DOTALL)
    replacement = '''.method public scanResults(I)Ljava/lang/String;
    .registers 3
    .param p1, "sid"    # I

    if-eqz p1, :first_page
    const/4 v0, 0x0
    return-object v0

    :first_page
    const-string v0, "SCAN_RESULTS"
    invoke-direct {p0, v0}, Landroid/net/wifi/WifiNative;->doStringCommandWithoutLogging(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    invoke-static {v0}, Landroid/net/wifi/Hd2ScanResults;->convert(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method'''
    text, count = scan_method.subn(replacement, text)
    assert count == 1
    native.write_text(text)

    helper = smali/'android/net/wifi/Hd2ScanResults.smali'
    helper.write_text(r'''.class final Landroid/net/wifi/Hd2ScanResults;
.super Ljava/lang/Object;

.method static convert(Ljava/lang/String;)Ljava/lang/String;
    .locals 9
    .param p0, "input"    # Ljava/lang/String;

    if-nez p0, :nonnull
    return-object p0

    :nonnull
    const-string v0, "\n"
    invoke-virtual {p0, v0}, Ljava/lang/String;->split(Ljava/lang/String;)[Ljava/lang/String;
    move-result-object v0
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V
    const/4 v2, 0x1
    array-length v3, v0

    :loop
    if-ge v2, v3, :done
    aget-object v4, v0, v2
    const-string v5, "\t"
    const/4 v6, 0x5
    invoke-virtual {v4, v5, v6}, Ljava/lang/String;->split(Ljava/lang/String;I)[Ljava/lang/String;
    move-result-object v4
    array-length v5, v4
    const/4 v6, 0x5
    if-lt v5, v6, :next

    const-string v5, "id="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    add-int/lit8 v5, v2, -0x1
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v5, "\nbssid="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v5, 0x0
    aget-object v5, v4, v5
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\nfreq="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v5, 0x1
    aget-object v5, v4, v5
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\nlevel="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v5, 0x2
    aget-object v5, v4, v5
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\ntsf=0\nflags="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v5, 0x3
    aget-object v5, v4, v5
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\nssid="
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v5, 0x4
    aget-object v5, v4, v5
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\n====\n"
    invoke-virtual {v1, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    :next
    add-int/lit8 v2, v2, 0x1
    goto :loop

    :done
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method
''')

    # This HD2 wpa_supplicant exposes one per-interface control socket.  Its
    # events therefore do not carry an IFNAME= prefix.  Qualcomm's monitor
    # routes unprefixed events to p2p0 by default, where they are discarded
    # because leo has no P2P interface.  Route them to the real interface.
    monitor = smali/'android/net/wifi/WifiMonitor$MonitorThread.smali'
    text = monitor.read_text()
    assert text.count('const-string/jumbo v3, "p2p0"') == 1
    assert text.count('const-string/jumbo v8, "p2p0"') == 2
    monitor.write_text(text.replace('"p2p0"', '"wlan0"'))

    # The leo supplicant can emit an extra SCAN-RESULTS event with an empty
    # payload. Smartisan clears the entire cache in that case, so a valid scan
    # flashes briefly and disappears. AOSP 4.4 keeps the last valid results.
    state_machine = smali/'android/net/wifi/WifiStateMachine.smali'
    text = state_machine.read_text()
    clear_on_empty = '''    move-object/from16 v0, p0

    iget-object v0, v0, Landroid/net/wifi/WifiStateMachine;->mScanResults:Ljava/util/List;

    move-object/from16 v27, v0

    invoke-interface/range {v27 .. v27}, Ljava/util/List;->clear()V

    .line 2011
'''
    assert text.count(clear_on_empty) == 1
    state_machine.write_text(text.replace(clear_on_empty, '    .line 2011\n'))

    dex = ROOT/'work/smartisan-compat/framework.dex'
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
        'change': ('WifiNative uses direct wlan0 commands, unprefixed supplicant '
                   'events are routed to wlan0, stable SCAN_RESULTS output is '
                   'converted for Android 4.4, and empty events preserve the '
                   'last valid AP list; Wi-Fi Direct is absent on HD2'),
    }
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
