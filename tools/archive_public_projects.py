#!/usr/bin/env python3
"""Export this shared porting workspace's code and redacted evidence to sibling repos."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def redact_string(value):
    value = re.sub(r'(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])',
                   '<MAC-REDACTED>', value)
    value = re.sub(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b', '<TOKEN-REDACTED>', value)
    return re.sub(r'(?i)([?&](?:token|access_token|signature|x-amz-signature|key)=)[^\s&"<>]+',
                  r'\1<REDACTED>', value)


def redact_json(value):
    if isinstance(value, dict):
        return {key: ('<REDACTED>' if re.fullmatch(
            r'(?i)(?:ssid|bssid|imei|imsi|iccid|serial|serial_number|password|passphrase|psk|access_token)', key)
            else redact_json(item)) for key, item in value.items()}
    if isinstance(value, list): return [redact_json(item) for item in value]
    if isinstance(value, str): return redact_string(value)
    return value


def redact_log(value):
    lines = []
    for line in value.splitlines(keepends=True):
        if re.search(r'(?i)(?:\b(?:SSID|BSSID|IMEI|IMSI|ICCID)\b|passphrase|authorization:|password\s*[:=]|\bpsk\s*=)', line):
            line = '[REDACTED: network/device identifier or credential-bearing diagnostic line]\n'
        lines.append(redact_string(line))
    return ''.join(lines)


def main():
    projects = [ROOT.parent/'hd2-smartisan-os', ROOT.parent/'hd2-sailfish-os']
    for repo in projects:
        for folder in ['tools', 'configs', 'logs', 'docs', 'screenshots', 'reference-sources', 'release']:
            (repo/folder).mkdir(exist_ok=True)
        for path in (ROOT/'tools').iterdir():
            if path.is_file() and path.suffix in ['.py', '.c', '.S']:
                shutil.copy2(path, repo/'tools'/path.name)
        shutil.copytree(ROOT/'configs', repo/'configs', dirs_exist_ok=True)
        shutil.copy2(ROOT/'sources.lock.json', repo/'sources.lock.json')
        shutil.copy2(ROOT/'README.md', repo/'docs/workspace-history.md')
        records = []
        for path in sorted((ROOT/'logs').rglob('*')):
            if not path.is_file() or path.suffix not in {'.log', '.txt', '.json', '.commands', '.config'}:
                continue
            if 'download' in path.name or path.name.endswith('-fast.log'): continue
            relative = path.relative_to(ROOT)
            original = path.read_text(errors='replace')
            if path.suffix == '.json':
                data = json.loads(original)
                clean = redact_json(data)
                public = json.dumps(clean, indent=2, ensure_ascii=False)+'\n'
                redacted = data != clean
            else:
                public = redact_log(original)
                redacted = public != original
            target = repo/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(public)
            records.append({'path': str(relative), 'redacted': redacted,
                            'sha256': hashlib.sha256(public.encode()).hexdigest()})
        (repo/'logs/archive-index.json').write_text(json.dumps(records, indent=2)+'\n')
        for path in (ROOT/'sources').iterdir():
            if path.is_file() and path.suffix in ['.c', '.cpp', '.json']:
                shutil.copy2(path, repo/'reference-sources'/path.name)
        (repo/'.gitignore').write_text('/downloads/\n/work/\n/out/\n/backups/\n/sources/\n__pycache__/\n*.pyc\n*.raw\n*.ext4\n*.zip\n*.tar.gz\n*.tar.bz2\n*.tmp\n')
        (repo/'requirements.txt').write_text('requests\npexpect\nPillow\n')
        (repo/'NOTICES.md').write_text('''# Attribution and source provenance

This is an unofficial HTC HD2 adaptation and engineering archive. Smartisan, Sailfish/Jolla, CyanogenMod, HTC, Qualcomm and upstream authors retain their respective rights. Original notices in reference code and ROM components continue to apply. No blanket relicensing of third-party firmware or code is intended.

`sources.lock.json` records upstream repositories, pinned commits, donor downloads and checksums. `reference-sources/` contains code used to investigate compatibility and retains its original licenses. The Sailfish release includes modified HD2 kernel source, configuration, local diff and compiler references. The Smartisan kernel is inherited from NexusHD2 V4.0 and was not rebuilt here.

The shared `tools/` and `configs/` snapshot preserves the complete porting workspace, including utilities for the companion OS. Use the entry points documented for this repository. ROM images are release assets, not Git objects.
''')
        (repo/'logs/README.md').write_text('''# Debug evidence archive

These records are a chronological engineering archive from the shared HD2 workspace. Earlier records can say UNTESTED/pending or describe failed experiments; current results are in README and release/BUILD-STATUS.json. archive-index.json identifies each archived log and its public SHA-256.

Network/device identifiers and credential-bearing lines have been redacted in public copies. Raw framebuffer buffers, device backups, user home directories, keys and network databases are not included. Local originals remain untouched. The phone clock was unset and reports 2014-05-20 in many logs; host capture names and monotonic times establish sequence.

Smartisan records use smartisan-/hd2- prefixes and the 024341 boot capture. Sailfish records use sailfish-/minisf- and later captures. Shared recovery records preserve FAT32/iOS investigation history; they are not instructions to repartition another card.
''')
        print(repo.name, len(records), 'text records', flush=True)
    sm, sf = projects
    for source, name in [('hd2-desktop-clean0.png', 'desktop.png'), ('hd2-tools-confirmed2.png', 'quick-controls.png')]:
        shutil.copy2(ROOT/'logs'/source, sm/'screenshots'/name)
    for source, name in [('release-apps.png', 'applications.png'), ('release-home.png', 'home.png'),
                         ('release-screenshot.png', 'camera-known-issue.png'), ('sailfish-reboot-frame.png', 'welcome.png')]:
        shutil.copy2(ROOT/'logs/sailfish-first-boot'/source, sf/'screenshots'/name)
    for repo, group, manifest in [(sm, 'smartisan-alpha0/HD2-SM20', 'smartisan-compat-manifest.json'),
                                  (sf, 'sailfish-alpha0/HD2-SF', 'sailfish-patch-manifest.json')]:
        shutil.copy2(ROOT/'out'/group/'BUILD-STATUS.json', repo/'release/BUILD-STATUS.json')
        shutil.copy2(ROOT/'logs'/manifest, repo/'release/PATCH-MANIFEST.json')
        shutil.copy2(ROOT/'out'/group/'SHA256SUMS', repo/'release/IMAGE-SHA256SUMS')
    shutil.copy2(ROOT/'logs/base-kernel.config', sm/'configs/base-kernel.config')
    shutil.copy2(ROOT/'work/kernel-sailfish/.config', sf/'configs/sailfish-built.config')
    (sf/'configs/sailfish-all-kernel-changes.patch').write_bytes(subprocess.check_output(
        ['git', '-C', str(ROOT/'sources/kernel-tytung'), 'diff', '--binary']))


if __name__ == '__main__': main()
